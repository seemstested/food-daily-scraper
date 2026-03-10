"""
GoFood (Gojek) scraper — Indonesia.

GoFood is deeply integrated into the Gojek super-app.  The mobile-web
version at gofood.co.id exposes a GraphQL-like API for listing pages.

Key observations (2025-Q4):
  - Listing endpoint: GET /api/v3/outlet/search?...
  - Auth: Bearer token stored in localStorage after first page load
  - WAF: AWS WAF + bot-score header injection
  - Rate limit: ~15 pages/min before soft-blocks

Strategy:
  1. First navigation seeds cookies + localStorage token
  2. Subsequent pages reuse the context (token persists)
  3. API responses intercepted and parsed directly
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from playwright.async_api import Page, Response

from scraper.core.base_scraper import BaseScraper
from scraper.exceptions import EmptyResponseError
from scraper.models import Platform, Restaurant
from scraper.utils.logger import get_logger
from scraper.utils.stealth import human_delay, human_scroll

logger = get_logger(__name__)

_BASE_URL = "https://gofood.co.id/jakarta/restaurants"
_API_PATTERN = re.compile(r"gofood\.co\.id/api|api\.gojek\.com/gofood", re.I)


class GoFoodScraper(BaseScraper):
    """
    Scraper for GoFood Indonesia (gofood.co.id).

    Unique challenges vs other platforms:
      - AWS WAF with bot-score challenge
      - Single-page app with infinite scroll (no explicit pagination)
      - Bearer token required for API calls (obtained from localStorage)
    """

    platform = Platform.GOFOOD

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._api_results: List[Dict] = []

    def build_listing_urls(self, location: str, pages: int) -> List[str]:
        """
        GoFood uses scroll-based pagination internally, but we model it
        as offset-based to stay consistent with the interface contract.
        Each 'page' is an independent navigation with a different offset.
        """
        base = f"https://gofood.co.id/{location}/restaurants"
        return [
            f"{base}?{urlencode({'page': i + 1, 'offset': i * 25})}"
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
        self._api_results.clear()

        try:
            page.on("response", self._handle_api_response)

            await self._safe_navigate(page, url)
            await human_delay(2_500, 5_000)

            # GoFood loads cards on scroll — trigger several scroll cycles
            for _ in range(3):
                await human_scroll(page, distance=2_000, steps=12)
                await human_delay(1_000, 2_000)

            restaurants: List[Restaurant] = []

            if self._api_results:
                restaurants = self._parse_api_results(self._api_results, url)
            else:
                logger.debug("No GoFood API data intercepted; falling back to HTML")
                restaurants = await self._parse_html(page, url)

            if not restaurants:
                await self._save_raw_html(page, url)
                raise EmptyResponseError(f"No restaurants from GoFood: {url}")

            await self._save_raw_html(page, url)
            logger.info("GoFood: extracted %d restaurants", len(restaurants))
            return restaurants

        finally:
            await context.close()

    # ── API interception ───────────────────────────────────────────────────────

    async def _handle_api_response(self, response: Response) -> None:
        if _API_PATTERN.search(response.url):
            try:
                body = await response.json()
                self._api_results.append(body)
                logger.debug("GoFood API intercepted: %s", response.url)
            except Exception as exc:
                logger.debug("GoFood API parse error: %s", exc)

    def _parse_api_results(
        self, results: List[Dict], source_url: str
    ) -> List[Restaurant]:
        restaurants: List[Restaurant] = []
        for result in results:
            outlets = (
                result.get("data", {}).get("outlets")
                or result.get("outlets")
                or result.get("result", {}).get("data", [])
                or []
            )
            for outlet in outlets:
                try:
                    restaurants.append(self._outlet_to_restaurant(outlet, source_url))
                except Exception as exc:
                    logger.warning("GoFood outlet parse error: %s", exc)
        return restaurants

    def _outlet_to_restaurant(self, outlet: Dict[str, Any], source_url: str) -> Restaurant:
        uid = str(outlet.get("id") or outlet.get("business_id", ""))
        name = outlet.get("name") or outlet.get("display_name", "")

        # Rating structure: { "average": 4.5, "count": 1234 }
        rating_obj = outlet.get("customer_rating") or outlet.get("rating") or {}
        if isinstance(rating_obj, dict):
            rating = rating_obj.get("average") or rating_obj.get("value")
            review_count = rating_obj.get("count") or rating_obj.get("total_reviews")
        else:
            rating = float(rating_obj) if rating_obj else None
            review_count = None

        # Delivery info
        delivery = outlet.get("delivery_info") or {}
        dt_min = delivery.get("min_eta") or outlet.get("eta_min")
        dt_max = delivery.get("max_eta") or outlet.get("eta_max")
        delivery_fee = delivery.get("fee") or outlet.get("delivery_fee")

        # Categories & tags
        categories = outlet.get("categories") or []
        cuisines = [
            c.get("name", c) if isinstance(c, dict) else str(c) for c in categories
        ]

        # Location
        loc = outlet.get("location") or outlet.get("address") or {}
        city = loc.get("city") if isinstance(loc, dict) else None
        address = loc.get("address") if isinstance(loc, dict) else str(loc)
        lat = (loc.get("coordinates") or {}).get("lat") if isinstance(loc, dict) else None
        lon = (loc.get("coordinates") or {}).get("lng") if isinstance(loc, dict) else None

        path = outlet.get("path") or outlet.get("slug") or uid
        url = f"https://gofood.co.id/{path}" if not path.startswith("http") else path

        return Restaurant(
            platform=self.platform,
            restaurant_id=uid,
            name=name,
            rating=float(rating) if rating is not None else None,
            review_count=int(review_count) if review_count is not None else None,
            delivery_time_min=int(dt_min) if dt_min is not None else None,
            delivery_time_max=int(dt_max) if dt_max is not None else None,
            delivery_fee=float(delivery_fee) if delivery_fee is not None else None,
            cuisines=cuisines,
            city=city,
            address=address,
            latitude=float(lat) if lat is not None else None,
            longitude=float(lon) if lon is not None else None,
            is_open=outlet.get("is_open", True),
            is_promoted=bool(outlet.get("is_promoted") or outlet.get("is_ad")),
            url=url,
            scrape_session_id=self._session_id,
        )

    # ── HTML fallback ──────────────────────────────────────────────────────────

    async def _parse_html(self, page: Page, url: str) -> List[Restaurant]:
        restaurants: List[Restaurant] = []
        cards = await page.query_selector_all(
            "[data-testid='outlet-card'], .outlet-card, article.restaurant-card"
        )
        for card in cards:
            try:
                name_el = await card.query_selector("h3, .name, [data-testid='outlet-name']")
                name = (await name_el.inner_text()).strip() if name_el else ""
                uid = await card.get_attribute("data-id") or name
                if not name:
                    continue
                restaurants.append(
                    Restaurant(
                        platform=self.platform,
                        restaurant_id=uid,
                        name=name,
                        url=url,
                        scrape_session_id=self._session_id,
                    )
                )
            except Exception as exc:
                logger.debug("GoFood HTML card error: %s", exc)
        return restaurants
