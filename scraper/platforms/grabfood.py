"""
GrabFood scraper — Jakarta / Indonesia.

GrabFood uses:
  - Server-Side Rendering for the listing page shell
  - Internal REST API (merchantService) for restaurant lists (JSON)
  - Playwright needed to bypass CloudFront WAF + obtain session cookies

Extraction strategy:
  1. Navigate listing page to obtain session cookies / tokens
  2. Intercept or replay the internal API call for restaurant cards
  3. Fall back to HTML parsing if API response structure changes

Reference endpoints (as of 2025-Q4, may change):
  https://food.grab.com/id/en/restaurants?search=&location=<city>
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlencode

from playwright.async_api import Page, Request, Response

from scraper.core.base_scraper import BaseScraper
from scraper.exceptions import EmptyResponseError, ParseError
from scraper.models import MenuItem, Platform, PriceRange, Restaurant
from scraper.utils.logger import get_logger
from scraper.utils.stealth import human_delay, human_scroll

logger = get_logger(__name__)

_BASE_ORIGIN = "https://food.grab.com"
_BASE_URL = "https://food.grab.com/id/en"
# Broad pattern — catches any XHR to GrabFood backend with merchant data
_API_PATTERN = re.compile(
    r"food\.grab\.com/(?:proxy/|grabfood-ims/|api/|grabmart/|merchantService/|portals/)",
    re.I,
)


class GrabFoodScraper(BaseScraper):
    """
    Scraper for GrabFood Indonesia.

    Anti-bot measures encountered:
      - CloudFront WAF fingerprinting
      - 429 rate limiting after ~30 req/min without delays
      - Occasional CAPTCHA on fresh IPs

    Mitigations:
      - Stealth JS patches (see utils/stealth.py)
      - Human-like delays (gaussian distribution)
      - Proxy rotation on 403/429
      - Session cookie reuse across pages
    """

    platform = Platform.GRABFOOD

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._intercepted_data: List[Dict] = []

    def build_listing_urls(self, location: str, pages: int) -> List[str]:
        """
        GrabFood paginates via offset parameter.
        Each page returns ~30 restaurants; offset increments by 30.
        """
        base = f"{_BASE_URL}/restaurants"
        return [
            f"{base}?{urlencode({'search': '', 'location': location, 'offset': i * 30})}"
            for i in range(pages)
        ]

    async def scrape_listing_page(self, url: str) -> List[Restaurant]:
        proxy = None
        if self._proxy_manager:
            try:
                proxy = self._proxy_manager.get_proxy()
            except Exception:
                pass

        context, page = await self._new_page(proxy)
        self._intercepted_data.clear()

        try:
            # Register API intercept before navigation
            page.on("response", self._handle_api_response)

            # networkidle waits for all XHR/fetch calls to finish
            await self._safe_navigate(page, url)
            await human_delay(2_000, 4_000)
            await human_scroll(page, distance=1_500, steps=10)
            await human_delay(1_500, 3_000)

            # Give any lazy XHR calls extra time to settle
            try:
                await page.wait_for_load_state("networkidle", timeout=8_000)
            except Exception:
                pass  # timeout is fine — proceed with what we have

            restaurants: List[Restaurant] = []

            # 1. Try __NEXT_DATA__ (SSR-embedded JSON — fastest, most reliable)
            restaurants = await self._parse_next_data(page, url)

            # 2. Fall back to intercepted XHR API responses
            if not restaurants and self._intercepted_data:
                logger.debug("Trying intercepted API data (%d responses)", len(self._intercepted_data))
                restaurants = self._parse_api_response(self._intercepted_data, url)

            # 3. Final fallback: raw DOM scraping
            if not restaurants:
                logger.debug("No API data intercepted, falling back to HTML parsing")
                restaurants = await self._parse_html(page, url)

            if not restaurants:
                await self._save_raw_html(page, url)
                raise EmptyResponseError(f"Zero restaurants extracted from {url}")

            await self._save_raw_html(page, url)
            logger.info("Extracted %d restaurants from %s", len(restaurants), url)
            return restaurants

        finally:
            try:
                await context.close()
            except Exception:
                pass

    # ── __NEXT_DATA__ extraction (primary method) ─────────────────────────────

    async def _parse_next_data(self, page: Page, source_url: str) -> List[Restaurant]:
        """Extract restaurant data from Next.js SSR __NEXT_DATA__ JSON blob."""
        try:
            raw = await page.evaluate(
                "() => { const el = document.getElementById('__NEXT_DATA__'); return el ? el.textContent : null; }"
            )
            if not raw:
                return []
            data = json.loads(raw)
            # Walk common Next.js paths where GrabFood stores restaurant cards
            candidates = [
                data.get("props", {}).get("pageProps", {}).get("initData", {}),
                data.get("props", {}).get("pageProps", {}),
                data,
            ]
            for root in candidates:
                merchants = (
                    root.get("merchantsList")
                    or root.get("merchants")
                    or root.get("searchResult", {}).get("searchMerchants")
                    or root.get("data", {}).get("merchants")
                )
                if merchants and isinstance(merchants, list):
                    logger.info("__NEXT_DATA__: found %d merchants", len(merchants))
                    results = []
                    for m in merchants:
                        try:
                            results.append(self._merchant_to_restaurant(m, source_url))
                        except Exception as exc:
                            logger.debug("Skipping merchant: %s", exc)
                    return results

            # Dump top-level pageProps keys to help debug structure
            page_props = data.get("props", {}).get("pageProps", {})
            logger.debug("__NEXT_DATA__ pageProps keys: %s", list(page_props.keys())[:15])
            return []
        except Exception as exc:
            logger.debug("__NEXT_DATA__ extraction failed: %s", exc)
            return []

    # ── API interception ───────────────────────────────────────────────────────

    async def _handle_api_response(self, response: Response) -> None:
        """Capture internal merchant API responses in-flight."""
        if not _API_PATTERN.search(response.url):
            return
        try:
            # Read body immediately — becomes unavailable after context closes
            body = await response.json()
            # Only store if it looks like it contains merchant data
            body_str = json.dumps(body)
            if "merchantID" in body_str or "merchant" in body_str.lower():
                self._intercepted_data.append(body)
                logger.debug("Intercepted API response from %s", response.url)
        except Exception as exc:
            logger.debug("Could not parse intercepted response: %s", exc)

    def _parse_api_response(
        self, data_list: List[Dict], source_url: str
    ) -> List[Restaurant]:
        """Parse intercepted API JSON into Restaurant models."""
        restaurants: List[Restaurant] = []
        for data in data_list:
            merchants = (
                data.get("data", {}).get("searchResult", {}).get("searchMerchants")
                or data.get("merchants")
                or []
            )
            for m in merchants:
                try:
                    restaurants.append(self._merchant_to_restaurant(m, source_url))
                except Exception as exc:
                    logger.warning("Skipping merchant (parse error): %s", exc)
        return restaurants

    def _merchant_to_restaurant(self, m: Dict[str, Any], source_url: str) -> Restaurant:
        """Map a raw merchant dict to a validated Restaurant model."""
        info = m.get("merchantBrief", m)
        uid = m.get("id") or m.get("merchantID", "")
        name = info.get("displayInfo", {}).get("primaryText") or m.get("name", "")
        rating = info.get("rating")
        review_count = info.get("vote_count") or info.get("reviewCount")

        # Delivery time: "25-35 min" → (25, 35)
        dt_raw = (
            m.get("estimatedDeliveryTime")
            or info.get("deliveryTime", "")
        )
        dmin, dmax = self._parse_delivery_time(str(dt_raw))

        cuisines_raw = info.get("cuisines") or m.get("tags") or []
        cuisines = (
            [c.get("name", c) if isinstance(c, dict) else c for c in cuisines_raw]
            if isinstance(cuisines_raw, list)
            else []
        )

        slug = m.get("addressInfo", {}).get("city", "").lower().replace(" ", "-")
        url = f"{_BASE_URL}/restaurant/{m.get('chain_id', uid)}"

        return Restaurant(
            platform=self.platform,
            restaurant_id=str(uid),
            name=name,
            slug=slug,
            rating=float(rating) if rating is not None else None,
            review_count=int(review_count) if review_count is not None else None,
            delivery_time_min=dmin,
            delivery_time_max=dmax,
            delivery_fee=m.get("lowestBasket") or m.get("deliveryFee"),
            cuisines=cuisines,
            city=m.get("addressInfo", {}).get("city"),
            address=m.get("addressInfo", {}).get("address"),
            latitude=m.get("latlng", {}).get("latitude"),
            longitude=m.get("latlng", {}).get("longitude"),
            is_open=m.get("isOnline", True),
            is_promoted=bool(m.get("adInfo")),
            url=url,
            scrape_session_id=self._session_id,
        )

    # ── HTML fallback ──────────────────────────────────────────────────────────

    async def _parse_html(self, page: Page, url: str) -> List[Restaurant]:
        """
        DOM-based extraction when API interception yields nothing.
        Selectors may need updating if GrabFood redesigns their frontend.
        """
        restaurants: List[Restaurant] = []
        seen_ids: set[str] = set()

        cards = await page.query_selector_all("[data-testid='vertical-card-component']")
        if not cards:
            cards = await page.query_selector_all(".restaurant-list-card")
        if not cards:
            cards = await page.query_selector_all("a[href*='/restaurant/']")

        for card in cards:
            try:
                href = await card.get_attribute("href") or ""
                if not href:
                    link_el = await card.query_selector("a[href*='/restaurant/']")
                    href = (await link_el.get_attribute("href")) if link_el else ""
                if not href or "/restaurant/" not in href:
                    continue

                uid_match = re.search(r"/restaurant/[^/]+/([^/?#]+)", href)
                uid = uid_match.group(1) if uid_match else ""
                if not uid:
                    continue
                if uid in seen_ids:
                    continue

                name_el = await card.query_selector(
                    "p.name, [data-testid='restaurant-name'], p[class*='name'], [class*='name___']"
                )
                name = (await name_el.inner_text()).strip() if name_el else ""
                if not name:
                    continue

                rating_el = await card.query_selector("[data-testid='rating'], [class*='rating']")
                rating_str = (await rating_el.inner_text()).strip() if rating_el else ""
                rating_match = re.search(r"\d+(?:\.\d+)?", rating_str)
                rating = float(rating_match.group(0)) if rating_match else None

                restaurant_url = href if href.startswith("http") else f"{_BASE_ORIGIN}{href}"

                restaurants.append(
                    Restaurant(
                        platform=self.platform,
                        restaurant_id=uid,
                        name=name,
                        rating=rating,
                        url=restaurant_url,
                        scrape_session_id=self._session_id,
                    )
                )
                seen_ids.add(uid)
            except Exception as exc:
                logger.debug("HTML card parse error: %s", exc)

        logger.debug("HTML fallback extracted %d restaurants", len(restaurants))
        return restaurants

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_delivery_time(raw: str) -> tuple[Optional[int], Optional[int]]:
        """Extract (min, max) minutes from strings like '25-35 min'."""
        match = re.search(r"(\d+)\s*[-–]\s*(\d+)", raw)
        if match:
            return int(match.group(1)), int(match.group(2))
        single = re.search(r"(\d+)", raw)
        if single:
            v = int(single.group(1))
            return v, v
        return None, None
