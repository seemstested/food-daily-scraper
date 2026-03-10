"""
Pydantic data models for scraped restaurant and menu data.
All data entering the pipeline must be validated through these models.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class Platform(str, Enum):
    GRABFOOD = "grabfood"
    SHOPEEFOOD = "shopeefood"
    GOFOOD = "gofood"


class PriceRange(str, Enum):
    BUDGET = "$"
    MID = "$$"
    PREMIUM = "$$$"
    LUXURY = "$$$$"


class MenuItem(BaseModel):
    """Represents a single menu item within a restaurant."""

    item_id: str = Field(..., min_length=1, description="Platform-specific item ID")
    name: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = Field(default=None, max_length=1000)
    price: float = Field(..., ge=0, description="Price in local currency (IDR)")
    original_price: Optional[float] = Field(default=None, ge=0)
    is_available: bool = Field(default=True)
    category: Optional[str] = Field(default=None, max_length=100)
    image_url: Optional[str] = Field(default=None)

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_whitespace(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v

    @model_validator(mode="after")
    def validate_discount(self) -> "MenuItem":
        if self.original_price is not None and self.original_price < self.price:
            raise ValueError("original_price must be >= discounted price")
        return self


class OperatingHours(BaseModel):
    day: str = Field(..., description="e.g. Monday, Tuesday")
    open_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    close_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    is_closed: bool = Field(default=False)


class Restaurant(BaseModel):
    """
    Core data model for a scraped restaurant listing.

    Enforces strict validation to ensure data quality downstream.
    All monetary values in IDR (Indonesian Rupiah).
    """

    platform: Platform
    restaurant_id: str = Field(..., min_length=1, description="Platform-specific restaurant ID")
    name: str = Field(..., min_length=1, max_length=300)
    slug: Optional[str] = Field(default=None, description="URL-friendly name")

    # Ratings & reviews
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    review_count: Optional[int] = Field(default=None, ge=0)

    # Logistics
    delivery_time_min: Optional[int] = Field(default=None, ge=0, description="Minutes")
    delivery_time_max: Optional[int] = Field(default=None, ge=0, description="Minutes")
    delivery_fee: Optional[float] = Field(default=None, ge=0)
    minimum_order: Optional[float] = Field(default=None, ge=0)

    # Classification
    cuisines: List[str] = Field(default_factory=list)
    price_range: Optional[PriceRange] = None
    tags: List[str] = Field(default_factory=list)

    # Location
    city: Optional[str] = Field(default=None, max_length=100)
    district: Optional[str] = Field(default=None, max_length=100)
    address: Optional[str] = Field(default=None, max_length=500)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)

    # Status
    is_open: Optional[bool] = Field(default=None)
    is_promoted: bool = Field(default=False)
    promo_label: Optional[str] = Field(default=None, max_length=200)

    # Menu
    menu_items: List[MenuItem] = Field(default_factory=list)
    menu_categories: List[str] = Field(default_factory=list)

    # URLs & media
    url: str = Field(..., description="Direct link to restaurant page")
    image_url: Optional[str] = Field(default=None)

    # Pipeline metadata
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    scrape_session_id: Optional[str] = Field(default=None)
    raw_data_path: Optional[str] = Field(default=None, description="Path to raw HTML/JSON backup")

    @field_validator("cuisines", "tags", mode="before")
    @classmethod
    def parse_list_from_string(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [c.strip() for c in v.split(",") if c.strip()]
        return v or []

    @field_validator("name", "city", "district", "address", mode="before")
    @classmethod
    def strip_string_fields(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v

    @model_validator(mode="after")
    def validate_delivery_time_range(self) -> "Restaurant":
        if self.delivery_time_min is not None and self.delivery_time_max is not None:
            if self.delivery_time_min > self.delivery_time_max:
                raise ValueError("delivery_time_min must be <= delivery_time_max")
        return self

    @property
    def delivery_time_str(self) -> Optional[str]:
        """Human-readable delivery time range."""
        if self.delivery_time_min is not None and self.delivery_time_max is not None:
            return f"{self.delivery_time_min}-{self.delivery_time_max} min"
        return None

    def to_flat_dict(self) -> Dict[str, Any]:
        """Flatten to a single-row dict for CSV export."""
        return {
            "platform": self.platform.value,
            "restaurant_id": self.restaurant_id,
            "name": self.name,
            "rating": self.rating,
            "review_count": self.review_count,
            "delivery_time": self.delivery_time_str,
            "delivery_fee": self.delivery_fee,
            "minimum_order": self.minimum_order,
            "cuisines": ", ".join(self.cuisines),
            "price_range": self.price_range.value if self.price_range else None,
            "city": self.city,
            "district": self.district,
            "address": self.address,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "is_open": self.is_open,
            "is_promoted": self.is_promoted,
            "promo_label": self.promo_label,
            "menu_item_count": len(self.menu_items),
            "url": self.url,
            "scraped_at": self.scraped_at.isoformat(),
        }


class ScrapeSession(BaseModel):
    """Metadata about a scraping session for monitoring and auditing."""

    session_id: str
    platform: Platform
    location: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    total_pages: int = Field(default=0)
    total_restaurants: int = Field(default=0)
    failed_pages: int = Field(default=0)
    blocked_count: int = Field(default=0)
    proxy_rotations: int = Field(default=0)
    status: str = Field(default="running")  # running | completed | failed

    @property
    def success_rate(self) -> float:
        total = self.total_pages + self.failed_pages
        if total == 0:
            return 0.0
        return round(self.total_pages / total * 100, 2)

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None
