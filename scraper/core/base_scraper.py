"""
Abstract base class for all platform scrapers.

Responsibilities:
  - Browser lifecycle management (launch / reuse / teardown)
  - Cookie / session management
  - Retry logic with exponential backoff (via tenacity)
  - Proxy assignment per page
  - Raw HTML archival
  - Session metrics collection

Concrete scrapers override:
  - scrape_listing_page(url) → List[Restaurant]
  - build_listing_urls(location, pages) → List[str]
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, List, Optional
from urllib.parse import urlparse

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from scraper.config import settings
from scraper.exceptions import (
    BlockedError,
    CaptchaError,
    EmptyResponseError,
    NetworkError,
    RateLimitError,
)
from scraper.models import Platform, Restaurant, ScrapeSession
from scraper.utils.logger import get_logger
from scraper.utils.proxy_manager import ProxyManager
from scraper.utils.stealth import apply_stealth, human_delay, random_viewport

logger = get_logger(__name__)


class BaseScraper(ABC):
    """
    Async context-manager scraper base.

    Usage::

        async with GrabFoodScraper() as scraper:
            restaurants = await scraper.scrape(location="jakarta", pages=5)
    """

    platform: Platform  # Must be set by subclass

    def __init__(
        self,
        proxy_manager: Optional[ProxyManager] = None,
        session_id: Optional[str] = None,
    ) -> None:
        self._proxy_manager = proxy_manager
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._session_id = session_id or str(uuid.uuid4())[:8]
        self._session = ScrapeSession(
            session_id=self._session_id,
            platform=self.platform,
            location="",
        )

    # ── Context manager ────────────────────────────────────────────────────────

    async def __aenter__(self) -> "BaseScraper":
        self._playwright = await async_playwright().start()
        await self._launch_browser()
        return self

    async def __aexit__(self, *_) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    # ── Public API ─────────────────────────────────────────────────────────────

    async def scrape(self, location: str, pages: int = 1) -> List[Restaurant]:
        """
        High-level entry point: scrape `pages` listing pages for `location`.

        Args:
            location: City / area slug used by the platform (e.g. "jakarta").
            pages:    Number of pagination pages to process.

        Returns:
            Deduplicated list of validated Restaurant objects.
        """
        self._session.location = location
        self._session.started_at = datetime.utcnow()

        urls = self.build_listing_urls(location, pages)
        logger.info(
            "Starting scrape",
            extra={
                "platform": self.platform.value,
                "location": location,
                "pages": pages,
                "session_id": self._session_id,
            },
        )

        results: List[Restaurant] = []
        seen_ids: set[str] = set()

        for i, url in enumerate(urls, start=1):
            logger.info("Scraping page %d/%d: %s", i, len(urls), url)
            try:
                page_results = await self._scrape_with_retry(url)
                new = [r for r in page_results if r.restaurant_id not in seen_ids]
                seen_ids.update(r.restaurant_id for r in new)
                results.extend(new)
                self._session.total_pages += 1
                self._session.total_restaurants += len(new)
            except RetryError as exc:
                logger.error("Page %d failed after all retries: %s", i, exc)
                self._session.failed_pages += 1

            if i < len(urls):
                await human_delay(
                    settings.rate_limit.page_delay_ms,
                    settings.rate_limit.page_delay_ms + 2_000,
                )

        self._session.finished_at = datetime.utcnow()
        self._session.status = "completed"
        logger.info(
            "Scrape finished",
            extra={
                "total": len(results),
                "success_rate": f"{self._session.success_rate}%",
                "duration_s": self._session.duration_seconds,
            },
        )
        return results

    @property
    def session(self) -> ScrapeSession:
        return self._session

    # ── Abstract interface ─────────────────────────────────────────────────────

    @abstractmethod
    def build_listing_urls(self, location: str, pages: int) -> List[str]:
        """Return ordered list of listing page URLs to scrape."""

    @abstractmethod
    async def scrape_listing_page(self, url: str) -> List[Restaurant]:
        """Parse a single listing page and return validated Restaurant objects."""

    # ── Retry wrapper ──────────────────────────────────────────────────────────

    async def _scrape_with_retry(self, url: str) -> List[Restaurant]:
        cfg = settings.retry

        @retry(
            stop=stop_after_attempt(cfg.max_attempts),
            wait=wait_exponential(
                multiplier=cfg.multiplier,
                min=cfg.wait_min,
                max=cfg.wait_max,
            ),
            retry=retry_if_exception_type((NetworkError, EmptyResponseError, RateLimitError)),
            before_sleep=lambda rs: logger.warning(
                "Retry %d/%d for %s after: %s",
                rs.attempt_number,
                cfg.max_attempts,
                url,
                rs.outcome.exception(),
            ),
            reraise=True,
        )
        async def _inner():
            proxy = None
            if self._proxy_manager:
                try:
                    proxy = self._proxy_manager.get_proxy()
                except Exception:
                    logger.warning("No proxy available, proceeding without")

            try:
                result = await self.scrape_listing_page(url)
                if proxy:
                    self._proxy_manager.mark_success(proxy)  # type: ignore[union-attr]
                return result
            except (BlockedError, CaptchaError):
                if proxy:
                    self._proxy_manager.mark_failure(proxy)  # type: ignore[union-attr]
                    self._session.proxy_rotations += 1
                raise
            except RateLimitError:
                if proxy:
                    self._proxy_manager.mark_failure(proxy)  # type: ignore[union-attr]
                raise

        return await _inner()

    # ── Browser helpers ────────────────────────────────────────────────────────

    async def _launch_browser(self) -> None:
        assert self._playwright is not None
        self._browser = await self._playwright.chromium.launch(
            headless=settings.browser.headless,
            slow_mo=settings.browser.slow_mo,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )
        logger.debug("Browser launched (headless=%s)", settings.browser.headless)

    async def _new_context(self, proxy: Optional[str] = None) -> BrowserContext:
        assert self._browser is not None
        width, height = random_viewport()
        ctx_kwargs = dict(
            user_agent=settings.browser.user_agent,
            viewport={"width": width, "height": height},
            locale="en-US",
            timezone_id="Asia/Jakarta",
            geolocation={"latitude": -6.2088, "longitude": 106.8456},  # Jakarta
            permissions=["geolocation"],
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        if proxy:
            # Parse proxy URL to extract credentials
            parsed = urlparse(proxy)
            proxy_dict = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
            if parsed.username and parsed.password:
                proxy_dict["username"] = parsed.username
                proxy_dict["password"] = parsed.password
                logger.debug("Proxy configured: %s", proxy_dict["server"])
            ctx_kwargs["proxy"] = proxy_dict  # type: ignore[assignment]
        return await self._browser.new_context(**ctx_kwargs)

    async def _new_page(self, proxy: Optional[str] = None) -> tuple[BrowserContext, Page]:
        context = await self._new_context(proxy)
        page = await context.new_page()
        await apply_stealth(page)
        page.set_default_timeout(settings.browser.timeout_ms)
        return context, page

    async def _safe_navigate(self, page: Page, url: str) -> None:
        """Navigate to URL and handle common HTTP error codes."""
        try:
            response = await page.goto(url, wait_until="networkidle", timeout=45_000)
        except Exception:
            # networkidle can timeout on pages with long-polling / websockets;
            # fall back to domcontentloaded which always fires.
            logger.debug("networkidle timeout for %s, retrying with domcontentloaded", url)
            response = await page.goto(url, wait_until="domcontentloaded")
        if response is None:
            raise NetworkError(f"No response from {url}")
        if response.status == 429:
            raise RateLimitError()
        if response.status in (403, 401):
            raise BlockedError(f"HTTP {response.status} on {url}")
        if response.status >= 500:
            raise NetworkError(f"Server error {response.status} on {url}")

    async def _save_raw_html(self, page: Page, url: str) -> Optional[Path]:
        """Persist raw HTML to disk for debugging / replay."""
        if not settings.storage.save_raw_html:
            return None
        try:
            content = await page.content()
            url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
            filename = f"{self.platform.value}_{self._session_id}_{url_hash}.html"
            path = settings.storage.raw_html_dir / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            logger.debug("Raw HTML saved: %s", path)
            return path
        except Exception as exc:
            logger.warning("Could not save raw HTML: %s", exc)
            return None
