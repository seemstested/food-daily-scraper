"""
Pytest configuration: shared fixtures, event loop setup, and mock helpers.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper.models import Platform, Restaurant
from scraper.utils.proxy_manager import ProxyManager


# ── Event loop ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


# ── Sample data fixtures ───────────────────────────────────────────────────────

@pytest.fixture()
def sample_restaurant() -> Restaurant:
    return Restaurant(
        platform=Platform.GRABFOOD,
        restaurant_id="rest-abc-123",
        name="Warung Sate Pak Budi",
        rating=4.5,
        review_count=1243,
        delivery_time_min=25,
        delivery_time_max=35,
        delivery_fee=15_000.0,
        cuisines=["Indonesian", "Sate", "Grilled"],
        city="Jakarta",
        district="Menteng",
        address="Jl. Menteng Raya No. 10, Jakarta",
        latitude=-6.186486,
        longitude=106.834091,
        is_open=True,
        url="https://food.grab.com/id/en/restaurant/warung-sate-pak-budi",
    )


@pytest.fixture()
def sample_restaurants(sample_restaurant: Restaurant) -> List[Restaurant]:
    extras = [
        Restaurant(
            platform=Platform.GRABFOOD,
            restaurant_id=f"rest-{i}",
            name=f"Restaurant {i}",
            rating=3.0 + i * 0.3,
            review_count=100 * i,
            delivery_time_min=20,
            delivery_time_max=40,
            delivery_fee=10_000.0,
            cuisines=["Indonesian"],
            city="Jakarta",
            url=f"https://food.grab.com/id/en/restaurant/restaurant-{i}",
        )
        for i in range(1, 6)
    ]
    return [sample_restaurant] + extras


@pytest.fixture()
def proxy_manager() -> ProxyManager:
    return ProxyManager(
        proxies=[
            "http://user:pass@proxy1.example.com:8080",
            "http://user:pass@proxy2.example.com:8080",
            "http://user:pass@proxy3.example.com:8080",
        ],
        max_failures=2,
        strategy="least_failed",
    )


# ── Fixtures directory ─────────────────────────────────────────────────────────

@pytest.fixture()
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture()
def grabfood_api_response(fixtures_dir: Path) -> dict:
    path = fixtures_dir / "grabfood_api_response.json"
    return json.loads(path.read_text())


@pytest.fixture()
def shopeefood_api_response(fixtures_dir: Path) -> dict:
    path = fixtures_dir / "shopeefood_api_response.json"
    return json.loads(path.read_text())
