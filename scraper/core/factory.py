"""
Scraper factory — resolves a platform name to the correct scraper class.

Usage::

    from scraper.core.factory import ScraperFactory
    async with ScraperFactory.create("grabfood", proxy_manager=pm) as scraper:
        results = await scraper.scrape("jakarta", pages=5)
"""

from __future__ import annotations

from typing import Optional, Type

from scraper.core.base_scraper import BaseScraper
from scraper.exceptions import ConfigurationError
from scraper.models import Platform
from scraper.utils.proxy_manager import ProxyManager


def _load_scrapers() -> dict[Platform, Type[BaseScraper]]:
    """Lazy-import scrapers to avoid circular imports at module load time."""
    from scraper.platforms.grabfood import GrabFoodScraper
    from scraper.platforms.gofood import GoFoodScraper
    from scraper.platforms.shopeefood import ShopeeFoodScraper

    return {
        Platform.GRABFOOD: GrabFoodScraper,
        Platform.SHOPEEFOOD: ShopeeFoodScraper,
        Platform.GOFOOD: GoFoodScraper,
    }


class ScraperFactory:
    @staticmethod
    def create(
        platform: str,
        proxy_manager: Optional[ProxyManager] = None,
        session_id: Optional[str] = None,
    ) -> BaseScraper:
        """
        Instantiate the scraper for the given platform.

        Args:
            platform:      Platform slug — 'grabfood', 'shopeefood', or 'gofood'.
            proxy_manager: Optional ProxyManager instance.
            session_id:    Optional session identifier for logging correlation.

        Returns:
            Uninitialised scraper instance (use as async context manager).

        Raises:
            ConfigurationError: Unknown platform slug.
        """
        try:
            platform_enum = Platform(platform.lower())
        except ValueError:
            valid = [p.value for p in Platform]
            raise ConfigurationError(
                f"Unknown platform '{platform}'. Valid options: {valid}"
            )

        registry = _load_scrapers()
        scraper_cls = registry[platform_enum]
        return scraper_cls(proxy_manager=proxy_manager, session_id=session_id)
