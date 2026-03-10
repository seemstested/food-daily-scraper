"""
Integration test for GrabFoodScraper using mocked Playwright.

These tests verify the full data extraction pipeline:
  page navigation → API interception → model validation → result list

The browser is fully mocked — no network calls are made.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper.models import Platform, Restaurant
from scraper.platforms.grabfood import GrabFoodScraper


@pytest.fixture()
def grabfood_raw_payload(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "grabfood_api_response.json").read_text())


@pytest.fixture()
def mock_playwright_page(grabfood_raw_payload: dict):
    """Return a mock Playwright Page that simulates API response interception."""
    page = AsyncMock()
    page.goto = AsyncMock(return_value=MagicMock(status=200))
    page.content = AsyncMock(return_value="<html><body>mock</body></html>")
    page.query_selector_all = AsyncMock(return_value=[])
    page.add_init_script = AsyncMock()
    page.set_default_timeout = MagicMock()
    page.mouse = AsyncMock()

    # Simulate on("response", ...) storing callback, not calling it automatically
    page.on = MagicMock()

    return page


class TestGrabFoodScraper:
    @pytest.mark.asyncio
    async def test_build_listing_urls(self):
        scraper = GrabFoodScraper()
        urls = scraper.build_listing_urls("jakarta", 3)
        assert len(urls) == 3
        for url in urls:
            assert "jakarta" in url
            assert "food.grab.com" in url

    @pytest.mark.asyncio
    async def test_build_listing_urls_offset_increments(self):
        scraper = GrabFoodScraper()
        urls = scraper.build_listing_urls("surabaya", 4)
        assert "offset=0" in urls[0]
        assert "offset=30" in urls[1]
        assert "offset=60" in urls[2]
        assert "offset=90" in urls[3]

    def test_parse_api_response_returns_restaurants(self, grabfood_raw_payload):
        scraper = GrabFoodScraper()
        restaurants = scraper._parse_api_response([grabfood_raw_payload], "https://food.grab.com")
        assert len(restaurants) == 3
        assert all(isinstance(r, Restaurant) for r in restaurants)

    def test_parse_api_response_platform_is_grabfood(self, grabfood_raw_payload):
        scraper = GrabFoodScraper()
        restaurants = scraper._parse_api_response([grabfood_raw_payload], "https://food.grab.com")
        assert all(r.platform == Platform.GRABFOOD for r in restaurants)

    def test_parse_api_response_names(self, grabfood_raw_payload):
        scraper = GrabFoodScraper()
        restaurants = scraper._parse_api_response([grabfood_raw_payload], "https://food.grab.com")
        names = [r.name for r in restaurants]
        assert "Warung Sate Pak Budi" in names
        assert "Sushi Tei" in names

    def test_parse_api_response_ratings(self, grabfood_raw_payload):
        scraper = GrabFoodScraper()
        restaurants = scraper._parse_api_response([grabfood_raw_payload], "https://food.grab.com")
        sate = next(r for r in restaurants if "Sate" in r.name)
        assert sate.rating == pytest.approx(4.5)
        assert sate.review_count == 1243

    def test_parse_api_response_delivery_time(self, grabfood_raw_payload):
        scraper = GrabFoodScraper()
        restaurants = scraper._parse_api_response([grabfood_raw_payload], "https://food.grab.com")
        sate = next(r for r in restaurants if "Sate" in r.name)
        assert sate.delivery_time_min == 25
        assert sate.delivery_time_max == 35

    def test_parse_api_response_promoted_flag(self, grabfood_raw_payload):
        scraper = GrabFoodScraper()
        restaurants = scraper._parse_api_response([grabfood_raw_payload], "https://food.grab.com")
        sushi = next(r for r in restaurants if "Sushi" in r.name)
        assert sushi.is_promoted is True
        sate = next(r for r in restaurants if "Sate" in r.name)
        assert sate.is_promoted is False

    def test_parse_delivery_time_range(self):
        assert GrabFoodScraper._parse_delivery_time("25-35 min") == (25, 35)

    def test_parse_delivery_time_em_dash(self):
        assert GrabFoodScraper._parse_delivery_time("25–35 min") == (25, 35)

    def test_parse_delivery_time_single_value(self):
        assert GrabFoodScraper._parse_delivery_time("30 min") == (30, 30)

    def test_parse_delivery_time_empty(self):
        assert GrabFoodScraper._parse_delivery_time("") == (None, None)

    def test_parse_delivery_time_no_match(self):
        assert GrabFoodScraper._parse_delivery_time("N/A") == (None, None)

    @pytest.mark.asyncio
    async def test_scrape_context_manager_lifecycle(self):
        """Verify __aenter__/__aexit__ manage browser lifecycle correctly."""
        with (
            patch("scraper.core.base_scraper.async_playwright") as mock_pw_fn,
        ):
            mock_pw = AsyncMock()
            mock_browser = AsyncMock()
            mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_pw_fn.return_value.__aenter__ = AsyncMock(return_value=mock_pw)
            mock_pw_fn.return_value.start = AsyncMock(return_value=mock_pw)

            scraper = GrabFoodScraper()
            scraper._playwright = mock_pw
            scraper._browser = mock_browser

            await scraper.__aexit__(None, None, None)
            mock_browser.close.assert_called_once()
