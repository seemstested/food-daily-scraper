"""
Unit tests for CSV, JSON, and Excel exporters.
"""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path
from typing import List

import pytest

from scraper.exporters.exporters import CSVExporter, JSONExporter
from scraper.models import Restaurant


@pytest.fixture()
def tmp_export_dir(tmp_path: Path) -> Path:
    return tmp_path / "exports"


class TestCSVExporter:
    def test_creates_file(self, sample_restaurants, tmp_export_dir):
        exporter = CSVExporter(tmp_export_dir)
        path = exporter.export(sample_restaurants, "test_export")
        assert path.exists()
        assert path.suffix == ".csv"

    def test_row_count_matches(self, sample_restaurants, tmp_export_dir):
        exporter = CSVExporter(tmp_export_dir)
        path = exporter.export(sample_restaurants, "row_count")
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == len(sample_restaurants)

    def test_header_contains_expected_columns(self, sample_restaurants, tmp_export_dir):
        exporter = CSVExporter(tmp_export_dir)
        path = exporter.export(sample_restaurants, "headers")
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
        for col in ("platform", "restaurant_id", "name", "rating", "url"):
            assert col in headers

    def test_platform_value_in_csv(self, sample_restaurant, tmp_export_dir):
        exporter = CSVExporter(tmp_export_dir)
        path = exporter.export([sample_restaurant], "platform_check")
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["platform"] == "grabfood"

    def test_creates_output_dir_if_missing(self, sample_restaurant, tmp_path):
        nested = tmp_path / "a" / "b" / "c"
        exporter = CSVExporter(nested)
        path = exporter.export([sample_restaurant], "nested_dir")
        assert path.exists()

    def test_empty_list_produces_header_only_file(self, tmp_export_dir):
        exporter = CSVExporter(tmp_export_dir)
        path = exporter.export([], "empty")
        with open(path, newline="", encoding="utf-8") as f:
            content = f.read()
        assert "platform" in content  # header present
        lines = [l for l in content.splitlines() if l.strip()]
        assert len(lines) == 1  # only header


class TestJSONExporter:
    def test_creates_json_file(self, sample_restaurants, tmp_export_dir):
        exporter = JSONExporter(tmp_export_dir)
        path = exporter.export(sample_restaurants, "test_json")
        assert path.exists()
        assert path.suffix == ".json"

    def test_valid_json_structure(self, sample_restaurants, tmp_export_dir):
        exporter = JSONExporter(tmp_export_dir)
        path = exporter.export(sample_restaurants, "valid_json")
        data = json.loads(path.read_text())
        assert isinstance(data, list)
        assert len(data) == len(sample_restaurants)

    def test_restaurant_fields_present(self, sample_restaurant, tmp_export_dir):
        exporter = JSONExporter(tmp_export_dir)
        path = exporter.export([sample_restaurant], "fields")
        data = json.loads(path.read_text())
        record = data[0]
        assert record["platform"] == "grabfood"
        assert record["name"] == "Warung Sate Pak Budi"
        assert isinstance(record["cuisines"], list)

    def test_unicode_preserved(self, tmp_export_dir):
        r = Restaurant(
            platform=__import__("scraper.models", fromlist=["Platform"]).Platform.GRABFOOD,
            restaurant_id="uni-1",
            name="Warung Mie Ïndahñ",
            url="https://food.grab.com",
        )
        exporter = JSONExporter(tmp_export_dir)
        path = exporter.export([r], "unicode")
        content = path.read_text(encoding="utf-8")
        assert "Warung Mie Ïndahñ" in content

    def test_empty_list_produces_empty_array(self, tmp_export_dir):
        exporter = JSONExporter(tmp_export_dir)
        path = exporter.export([], "empty_json")
        data = json.loads(path.read_text())
        assert data == []
