"""
ShopeeFood scraper — Indonesia.

ShopeeFood (formerly Shopee Food / FoodPanda-like structure) exposes a
REST JSON API at dish-count/merchant list endpoints.  The site uses a
React SPA; the API is called on page load and is interceptable.

Endpoint pattern (as of 2025-Q4):
  POST https://mall.shopee.co.id/api/v4/food/delivery/get_homepage_list
  GET  https://food.shopee.co.id/api/v1/feeds/...

Note: API paths change frequently — always validate against live traffic
via browser devtools before a new deployment.
"""

from __future__ import annotations

import json
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

_BASE_URL = "https://shopee.co.id/food"
_API_PATTERN = re.compile(
    r"shopee\.co\.id/api/v\d+/food|food\.shopee\.co\.id/api", re.I
)


class ShopeeFoodScraper(BaseScraper):
    """
    Scraper for ShopeeFood Indonesia.

    Anti-bot measures encountered:
      - CloudFlare protection (CF-Clearance cookie required)
      - SameSite cookie restrictions on API calls
      - Aggressive rate limiting (< 20 req/min recommended)

    Mitigations:
      - Full Playwright browser session to obtain CF cookies
      - Slow scrolling to trigger lazy-load API calls
      - Randomised request headers and viewport
    """

    platform = Platform.SHOPEEFOOD

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._intercepted_payloads: List[Dict] = []

    def build_listing_urls(self, location: str, pages: int) -> List[str]:
        """
        ShopeeFood encodes location as city slug and uses page-based pagination.
        """
        return [
            f"{_BASE_URL}/{location}?{urlencode({'page': i + 1})}"
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
        self._intercepted_payloads.clear()

        try:
            page.on("response", self._handle_api_response)

            await self._safe_navigate(page, url)
            await human_delay(2_000, 4_500)

            # Trigger lazy-loaded restaurant cards by scrolling
            await human_scroll(page, distance=3_000, steps=15)
            await human_delay(1_500, 3_000)

            restaurants: List[Restaurant] = []

            if self._intercepted_payloads:
                restaurants = self._parse_api_payloads(self._intercepted_payloads, url)
            else:
                logger.debug("No ShopeeFood API data; falling back to HTML")
                restaurants = await self._parse_html(page, url)

            if not restaurants:
                await self._save_raw_html(page, url)
                raise EmptyResponseError(f"No restaurants from ShopeeFood: {url}")

            await self._save_raw_html(page, url)
            logger.info("ShopeeFood: extracted %d restaurants", len(restaurants))
            return restaurants

        finally:
            await context.close()

    # ── API interception ───────────────────────────────────────────────────────

    async def _handle_api_response(self, response: Response) -> None:
        if _API_PATTERN.search(response.url):
            try:
                body = await response.json()
                self._intercepted_payloads.append(body)
                logger.debug("ShopeeFood API intercepted: %s", response.url)
            except Exception as exc:
                logger.debug("ShopeeFood response parse failed: %s", exc)

    def _parse_api_payloads(
        self, payloads: List[Dict], source_url: str
    ) -> List[Restaurant]:
        restaurants: List[Restaurant] = []
        for payload in payloads:
            # Structure varies by API version; try common paths
            items = (
                payload.get("data", {}).get("items")
                or payload.get("result", {}).get("shops")
                or payload.get("shops")
                or []
            )
            for item in items:
                try:
                    restaurants.append(self._item_to_restaurant(item, source_url))
                except Exception as exc:
                    logger.warning("ShopeeFood item parse error: %s", exc)
        return restaurants

    def _item_to_restaurant(self, item: Dict[str, Any], source_url: str) -> Restaurant:
        shop_id = str(item.get("shopid") or item.get("id", ""))
        name = item.get("name") or item.get("shop_name", "")
        rating = item.get("rating") or item.get("score")
        review_count = item.get("rating_count") or item.get("num_ratings")

        min_time = item.get("min_delivery_time") or item.get("estimated_time")
        max_time = item.get("max_delivery_time")
        delivery_fee = item.get("delivery_fee") or item.get("shipping_fee")
        min_order = item.get("min_order_price")

        cuisines_raw = item.get("cuisine_tags") or item.get("tags") or []
        cuisines = [
            t.get("tag_name", t) if isinstance(t, dict) else str(t)
            for t in cuisines_raw
        ]

        city = item.get("city") or item.get("district")
        address = item.get("address")
        lat = item.get("latitude") or (item.get("coord") or {}).get("lat")
        lon = item.get("longitude") or (item.get("coord") or {}).get("lng")

        shop_info = item.get("shopee_food_info") or {}
        url = (
            f"https://shopee.co.id/food/{item.get('slug', shop_id)}"
            if item.get("slug")
            else source_url
        )

        return Restaurant(
            platform=self.platform,
            restaurant_id=shop_id,
            name=name,
            rating=float(rating) if rating is not None else None,
            review_count=int(review_count) if review_count is not None else None,
            delivery_time_min=int(min_time) if min_time is not None else None,
            delivery_time_max=int(max_time) if max_time is not None else None,
            delivery_fee=float(delivery_fee) if delivery_fee is not None else None,
            minimum_order=float(min_order) if min_order is not None else None,
            cuisines=cuisines,
            city=city,
            address=address,
            latitude=float(lat) if lat is not None else None,
            longitude=float(lon) if lon is not None else None,
            is_open=item.get("is_open", True),
            url=url,
            scrape_session_id=self._session_id,
        )

    # ── HTML fallback ──────────────────────────────────────────────────────────

    async def _parse_html(self, page: Page, url: str) -> List[Restaurant]:
        restaurants: List[Restaurant] = []
        cards = await page.query_selector_all(
            ".shopee-food-restaurant-card, [data-sqe='restaurant-card']"
        )
        for card in cards:
            try:
                name_el = await card.query_selector(".restaurant-name, h3")
                name = (await name_el.inner_text()).strip() if name_el else ""
                uid = await card.get_attribute("data-id") or name
                if not name:
                    continue
                restaurants.append(
                    Restaurant(
                        platform=self.platform,
                        restaurant_id=uid or name,
                        name=name,
                        url=url,
                        scrape_session_id=self._session_id,
                    )
                )
            except Exception as exc:
                logger.debug("ShopeeFood HTML card error: %s", exc)
        return restaurants
