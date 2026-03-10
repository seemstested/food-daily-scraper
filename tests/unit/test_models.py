"""
Unit tests for Pydantic data models.
Covers validation rules, edge cases, and computed properties.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from scraper.models import MenuItem, Platform, PriceRange, Restaurant, ScrapeSession


class TestRestaurantModel:
    def test_minimal_valid_restaurant(self):
        r = Restaurant(
            platform=Platform.GRABFOOD,
            restaurant_id="abc-123",
            name="Test Restaurant",
            url="https://food.grab.com/id/en/restaurant/test",
        )
        assert r.platform == Platform.GRABFOOD
        assert r.cuisines == []
        assert r.menu_items == []

    def test_full_valid_restaurant(self, sample_restaurant):
        assert sample_restaurant.rating == 4.5
        assert sample_restaurant.delivery_time_str == "25-35 min"
        assert "Indonesian" in sample_restaurant.cuisines

    def test_rating_out_of_range_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            Restaurant(
                platform=Platform.SHOPEEFOOD,
                restaurant_id="x",
                name="Bad",
                rating=5.5,  # > 5 is invalid
                url="https://shopee.co.id",
            )
        assert "rating" in str(exc_info.value)

    def test_negative_rating_raises(self):
        with pytest.raises(ValidationError):
            Restaurant(
                platform=Platform.GOFOOD,
                restaurant_id="y",
                name="Bad",
                rating=-0.1,
                url="https://gofood.co.id",
            )

    def test_delivery_time_min_gt_max_raises(self):
        with pytest.raises(ValidationError):
            Restaurant(
                platform=Platform.GRABFOOD,
                restaurant_id="z",
                name="Bad",
                delivery_time_min=40,
                delivery_time_max=20,  # min > max
                url="https://food.grab.com",
            )

    def test_cuisines_parsed_from_string(self):
        r = Restaurant(
            platform=Platform.GRABFOOD,
            restaurant_id="c1",
            name="Fusion Place",
            cuisines="Indonesian, Japanese, Fusion",
            url="https://food.grab.com",
        )
        assert r.cuisines == ["Indonesian", "Japanese", "Fusion"]

    def test_name_stripped_of_whitespace(self):
        r = Restaurant(
            platform=Platform.GRABFOOD,
            restaurant_id="c2",
            name="  Padded Name  ",
            url="https://food.grab.com",
        )
        assert r.name == "Padded Name"

    def test_to_flat_dict_keys(self, sample_restaurant):
        flat = sample_restaurant.to_flat_dict()
        for key in ("platform", "restaurant_id", "name", "rating", "cuisines", "url"):
            assert key in flat

    def test_to_flat_dict_cuisines_joined(self, sample_restaurant):
        flat = sample_restaurant.to_flat_dict()
        assert "Indonesian" in flat["cuisines"]
        assert isinstance(flat["cuisines"], str)

    def test_delivery_time_str_none_when_unset(self):
        r = Restaurant(
            platform=Platform.GOFOOD,
            restaurant_id="dt1",
            name="NoTime",
            url="https://gofood.co.id",
        )
        assert r.delivery_time_str is None

    def test_latitude_longitude_bounds(self):
        with pytest.raises(ValidationError):
            Restaurant(
                platform=Platform.GRABFOOD,
                restaurant_id="geo1",
                name="OOB",
                latitude=95.0,  # > 90
                url="https://food.grab.com",
            )

    def test_platform_enum_values(self):
        assert Platform.GRABFOOD.value == "grabfood"
        assert Platform.SHOPEEFOOD.value == "shopeefood"
        assert Platform.GOFOOD.value == "gofood"


class TestMenuItemModel:
    def test_valid_menu_item(self):
        item = MenuItem(
            item_id="item-001",
            name="Sate Ayam",
            price=35_000.0,
            category="Grilled",
        )
        assert item.is_available is True

    def test_negative_price_raises(self):
        with pytest.raises(ValidationError):
            MenuItem(item_id="bad", name="Free Food", price=-1.0)

    def test_original_price_less_than_price_raises(self):
        with pytest.raises(ValidationError):
            MenuItem(
                item_id="disc",
                name="Discounted",
                price=50_000.0,
                original_price=30_000.0,  # original < actual → invalid
            )

    def test_valid_discount(self):
        item = MenuItem(
            item_id="sale",
            name="Sale Item",
            price=30_000.0,
            original_price=50_000.0,
        )
        assert item.original_price == 50_000.0


class TestScrapeSession:
    def test_success_rate_no_pages(self):
        s = ScrapeSession(session_id="s1", platform=Platform.GRABFOOD, location="jakarta")
        assert s.success_rate == 0.0

    def test_success_rate_calculation(self):
        s = ScrapeSession(
            session_id="s2",
            platform=Platform.GRABFOOD,
            location="jakarta",
            total_pages=9,
            failed_pages=1,
        )
        assert s.success_rate == 90.0

    def test_duration_none_when_not_finished(self):
        s = ScrapeSession(session_id="s3", platform=Platform.GOFOOD, location="bali")
        assert s.duration_seconds is None
