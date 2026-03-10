"""
SQLite storage backend with optional PostgreSQL support.

Schema:
  restaurants — one row per scraped restaurant
  scrape_sessions — audit log for each run

Design choices:
  - SQLite by default (zero-config, portable)
  - Upsert semantics: re-runs update existing records, never duplicate
  - PostgreSQL activated via SCRAPER_STORAGE_BACKEND=postgres env var
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional

from scraper.exceptions import StorageError
from scraper.models import Platform, Restaurant, ScrapeSession
from scraper.utils.logger import get_logger

logger = get_logger(__name__)

_DDL_RESTAURANTS = """
CREATE TABLE IF NOT EXISTS restaurants (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    platform          TEXT    NOT NULL,
    restaurant_id     TEXT    NOT NULL,
    name              TEXT    NOT NULL,
    slug              TEXT,
    rating            REAL,
    review_count      INTEGER,
    delivery_time_min INTEGER,
    delivery_time_max INTEGER,
    delivery_fee      REAL,
    minimum_order     REAL,
    cuisines          TEXT,          -- JSON array
    price_range       TEXT,
    city              TEXT,
    district          TEXT,
    address           TEXT,
    latitude          REAL,
    longitude         REAL,
    is_open           INTEGER,
    is_promoted       INTEGER        DEFAULT 0,
    promo_label       TEXT,
    menu_item_count   INTEGER        DEFAULT 0,
    url               TEXT,
    image_url         TEXT,
    scrape_session_id TEXT,
    scraped_at        TEXT           NOT NULL,
    UNIQUE (platform, restaurant_id)
);
"""

_DDL_SESSIONS = """
CREATE TABLE IF NOT EXISTS scrape_sessions (
    session_id        TEXT PRIMARY KEY,
    platform          TEXT,
    location          TEXT,
    started_at        TEXT,
    finished_at       TEXT,
    total_pages       INTEGER DEFAULT 0,
    total_restaurants INTEGER DEFAULT 0,
    failed_pages      INTEGER DEFAULT 0,
    blocked_count     INTEGER DEFAULT 0,
    proxy_rotations   INTEGER DEFAULT 0,
    status            TEXT    DEFAULT 'running'
);
"""

_DDL_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_rest_platform ON restaurants (platform);",
    "CREATE INDEX IF NOT EXISTS idx_rest_city ON restaurants (city);",
    "CREATE INDEX IF NOT EXISTS idx_rest_scraped_at ON restaurants (scraped_at);",
]


class SQLiteStorage:
    """
    Persistent store backed by a local SQLite file.

    Args:
        db_path: Filesystem path to the .db file.  Created if absent.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # ── Schema ─────────────────────────────────────────────────────────────────

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(_DDL_RESTAURANTS)
            conn.execute(_DDL_SESSIONS)
            for idx in _DDL_INDEXES:
                conn.execute(idx)
        logger.debug("SQLite schema initialised: %s", self.db_path)

    # ── Restaurant CRUD ────────────────────────────────────────────────────────

    def upsert_restaurants(self, restaurants: List[Restaurant]) -> int:
        """
        Insert or update restaurant records (upsert by platform + restaurant_id).

        Returns:
            Number of rows affected.
        """
        rows = [self._to_row(r) for r in restaurants]
        sql = """
            INSERT INTO restaurants (
                platform, restaurant_id, name, slug, rating, review_count,
                delivery_time_min, delivery_time_max, delivery_fee, minimum_order,
                cuisines, price_range, city, district, address,
                latitude, longitude, is_open, is_promoted, promo_label,
                menu_item_count, url, image_url, scrape_session_id, scraped_at
            ) VALUES (
                :platform, :restaurant_id, :name, :slug, :rating, :review_count,
                :delivery_time_min, :delivery_time_max, :delivery_fee, :minimum_order,
                :cuisines, :price_range, :city, :district, :address,
                :latitude, :longitude, :is_open, :is_promoted, :promo_label,
                :menu_item_count, :url, :image_url, :scrape_session_id, :scraped_at
            )
            ON CONFLICT (platform, restaurant_id) DO UPDATE SET
                name              = excluded.name,
                rating            = excluded.rating,
                review_count      = excluded.review_count,
                delivery_time_min = excluded.delivery_time_min,
                delivery_time_max = excluded.delivery_time_max,
                delivery_fee      = excluded.delivery_fee,
                delivery_fee      = excluded.delivery_fee,
                cuisines          = excluded.cuisines,
                city              = excluded.city,
                is_open           = excluded.is_open,
                scrape_session_id = excluded.scrape_session_id,
                scraped_at        = excluded.scraped_at
        """
        with self._conn() as conn:
            conn.executemany(sql, rows)
        logger.debug("Upserted %d restaurants", len(rows))
        return len(rows)

    def get_restaurants(
        self,
        platform: Optional[Platform] = None,
        city: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 10_000,
    ) -> List[Restaurant]:
        """Query stored restaurants with optional filters."""
        clauses, params = [], {}
        if platform:
            clauses.append("platform = :platform")
            params["platform"] = platform.value
        if city:
            clauses.append("LOWER(city) = LOWER(:city)")
            params["city"] = city
        if since:
            clauses.append("scraped_at >= :since")
            params["since"] = since.isoformat()

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM restaurants {where} LIMIT :limit"
        params["limit"] = limit

        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()

        return [self._from_row(dict(r)) for r in rows]

    # ── Session CRUD ───────────────────────────────────────────────────────────

    def save_session(self, session: ScrapeSession) -> None:
        sql = """
            INSERT OR REPLACE INTO scrape_sessions VALUES (
                :session_id, :platform, :location, :started_at, :finished_at,
                :total_pages, :total_restaurants, :failed_pages,
                :blocked_count, :proxy_rotations, :status
            )
        """
        with self._conn() as conn:
            conn.execute(
                sql,
                {
                    "session_id": session.session_id,
                    "platform": session.platform.value,
                    "location": session.location,
                    "started_at": session.started_at.isoformat(),
                    "finished_at": session.finished_at.isoformat() if session.finished_at else None,
                    "total_pages": session.total_pages,
                    "total_restaurants": session.total_restaurants,
                    "failed_pages": session.failed_pages,
                    "blocked_count": session.blocked_count,
                    "proxy_rotations": session.proxy_rotations,
                    "status": session.status,
                },
            )
        logger.debug("Session %s saved", session.session_id)

    # ── Helpers ────────────────────────────────────────────────────────────────

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception as exc:
            conn.rollback()
            raise StorageError(f"Database error: {exc}") from exc
        finally:
            conn.close()

    @staticmethod
    def _to_row(r: Restaurant) -> dict:
        return {
            "platform": r.platform.value,
            "restaurant_id": r.restaurant_id,
            "name": r.name,
            "slug": r.slug,
            "rating": r.rating,
            "review_count": r.review_count,
            "delivery_time_min": r.delivery_time_min,
            "delivery_time_max": r.delivery_time_max,
            "delivery_fee": r.delivery_fee,
            "minimum_order": r.minimum_order,
            "cuisines": json.dumps(r.cuisines),
            "price_range": r.price_range.value if r.price_range else None,
            "city": r.city,
            "district": r.district,
            "address": r.address,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "is_open": int(r.is_open) if r.is_open is not None else None,
            "is_promoted": int(r.is_promoted),
            "promo_label": r.promo_label,
            "menu_item_count": len(r.menu_items),
            "url": r.url,
            "image_url": r.image_url,
            "scrape_session_id": r.scrape_session_id,
            "scraped_at": r.scraped_at.isoformat(),
        }

    @staticmethod
    def _from_row(row: dict) -> Restaurant:
        cuisines = json.loads(row.get("cuisines") or "[]")
        return Restaurant(
            platform=Platform(row["platform"]),
            restaurant_id=row["restaurant_id"],
            name=row["name"],
            slug=row.get("slug"),
            rating=row.get("rating"),
            review_count=row.get("review_count"),
            delivery_time_min=row.get("delivery_time_min"),
            delivery_time_max=row.get("delivery_time_max"),
            delivery_fee=row.get("delivery_fee"),
            minimum_order=row.get("minimum_order"),
            cuisines=cuisines,
            city=row.get("city"),
            district=row.get("district"),
            address=row.get("address"),
            latitude=row.get("latitude"),
            longitude=row.get("longitude"),
            is_open=bool(row["is_open"]) if row.get("is_open") is not None else None,
            is_promoted=bool(row.get("is_promoted", 0)),
            promo_label=row.get("promo_label"),
            url=row["url"],
            image_url=row.get("image_url"),
            scrape_session_id=row.get("scrape_session_id"),
            scraped_at=datetime.fromisoformat(row["scraped_at"]),
        )
