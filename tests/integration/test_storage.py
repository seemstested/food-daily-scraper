"""
Integration tests for SQLiteStorage.
Uses a real (in-memory / temp file) SQLite database.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from scraper.models import Platform, ScrapeSession
from scraper.storage.sqlite_storage import SQLiteStorage


@pytest.fixture()
def db(tmp_path: Path) -> SQLiteStorage:
    return SQLiteStorage(tmp_path / "test.db")


class TestUpsertRestaurants:
    def test_inserts_all_records(self, db, sample_restaurants):
        count = db.upsert_restaurants(sample_restaurants)
        assert count == len(sample_restaurants)

    def test_upsert_does_not_duplicate(self, db, sample_restaurant):
        db.upsert_restaurants([sample_restaurant])
        db.upsert_restaurants([sample_restaurant])  # second insert = update
        results = db.get_restaurants()
        # Still only one record for this restaurant_id
        matching = [r for r in results if r.restaurant_id == sample_restaurant.restaurant_id]
        assert len(matching) == 1

    def test_upsert_updates_rating(self, db, sample_restaurant):
        db.upsert_restaurants([sample_restaurant])
        updated = sample_restaurant.model_copy(update={"rating": 3.1})
        db.upsert_restaurants([updated])
        results = db.get_restaurants()
        stored = next(r for r in results if r.restaurant_id == sample_restaurant.restaurant_id)
        assert stored.rating == pytest.approx(3.1, abs=0.01)

    def test_cuisines_round_trip(self, db, sample_restaurant):
        db.upsert_restaurants([sample_restaurant])
        results = db.get_restaurants()
        stored = next(r for r in results if r.restaurant_id == sample_restaurant.restaurant_id)
        assert set(stored.cuisines) == set(sample_restaurant.cuisines)


class TestQueryFilters:
    def test_filter_by_platform(self, db, sample_restaurants):
        db.upsert_restaurants(sample_restaurants)
        results = db.get_restaurants(platform=Platform.GRABFOOD)
        assert all(r.platform == Platform.GRABFOOD for r in results)

    def test_filter_by_city(self, db, sample_restaurants):
        db.upsert_restaurants(sample_restaurants)
        results = db.get_restaurants(city="Jakarta")
        assert all(r.city is not None for r in results)

    def test_city_filter_case_insensitive(self, db, sample_restaurant):
        db.upsert_restaurants([sample_restaurant])
        results_upper = db.get_restaurants(city="JAKARTA")
        results_lower = db.get_restaurants(city="jakarta")
        assert len(results_upper) == len(results_lower)

    def test_limit_respected(self, db, sample_restaurants):
        db.upsert_restaurants(sample_restaurants)
        results = db.get_restaurants(limit=3)
        assert len(results) <= 3

    def test_empty_db_returns_empty_list(self, db):
        assert db.get_restaurants() == []


class TestScrapeSessionStorage:
    def test_save_and_retrieve_session(self, db):
        session = ScrapeSession(
            session_id="test-sess-001",
            platform=Platform.GRABFOOD,
            location="jakarta",
            total_pages=5,
            total_restaurants=142,
            failed_pages=0,
            status="completed",
            started_at=datetime(2026, 3, 9, 10, 0, 0),
            finished_at=datetime(2026, 3, 9, 10, 5, 30),
        )
        db.save_session(session)

        with db._conn() as conn:
            conn.row_factory = __import__("sqlite3").Row
            row = conn.execute(
                "SELECT * FROM scrape_sessions WHERE session_id = ?",
                ("test-sess-001",),
            ).fetchone()

        assert row is not None
        assert row["total_restaurants"] == 142
        assert row["status"] == "completed"

    def test_session_upsert_on_duplicate(self, db):
        session = ScrapeSession(
            session_id="dup-sess",
            platform=Platform.GOFOOD,
            location="bali",
            status="running",
        )
        db.save_session(session)

        session_updated = session.model_copy(update={"status": "completed", "total_restaurants": 50})
        db.save_session(session_updated)

        with db._conn() as conn:
            conn.row_factory = __import__("sqlite3").Row
            row = conn.execute(
                "SELECT * FROM scrape_sessions WHERE session_id = ?", ("dup-sess",)
            ).fetchone()

        assert row["status"] == "completed"
        assert row["total_restaurants"] == 50
