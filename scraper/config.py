"""
Centralised configuration management.

Priority order (highest → lowest):
  1. Environment variables  (SCRAPER_PROXY_LIST, etc.)
  2. YAML config file       (config/settings.yaml)
  3. Defaults baked into this module

Usage:
    from scraper.config import settings
    print(settings.browser.headless)
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent


class BrowserSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCRAPER_BROWSER_")

    headless: bool = True
    slow_mo: int = Field(default=0, ge=0, description="Milliseconds to slow Playwright actions")
    timeout_ms: int = Field(default=30_000, ge=5_000)
    viewport_width: int = Field(default=1920)
    viewport_height: int = Field(default=1080)
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )


class ProxySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCRAPER_PROXY_")

    enabled: bool = False
    proxies: List[str] = Field(default_factory=list)
    max_failures: int = Field(default=3, ge=1)
    rotation_strategy: str = Field(default="least_failed")  # least_failed | round_robin | random

    @field_validator("proxies", mode="before")
    @classmethod
    def parse_proxy_string(cls, v):
        if isinstance(v, str):
            return [p.strip() for p in v.split(",") if p.strip()]
        return v


class RetrySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCRAPER_RETRY_")

    max_attempts: int = Field(default=3, ge=1, le=10)
    wait_min: float = Field(default=4.0, ge=0)
    wait_max: float = Field(default=10.0, ge=0)
    multiplier: float = Field(default=1.5, ge=1)


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCRAPER_STORAGE_")

    backend: str = Field(default="sqlite")  # sqlite | postgres
    sqlite_path: Path = Field(default=ROOT_DIR / "data" / "scraper.db")
    postgres_dsn: Optional[str] = Field(default=None)
    save_raw_html: bool = Field(default=True, description="Persist raw HTML for debugging")
    raw_html_dir: Path = Field(default=ROOT_DIR / "data" / "raw")


class RateLimitSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCRAPER_RATE_")

    min_delay_ms: int = Field(default=1_500, ge=0)
    max_delay_ms: int = Field(default=4_000, ge=0)
    page_delay_ms: int = Field(default=3_000, ge=0, description="Extra delay between pages")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SCRAPER_",
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: str = Field(default="INFO")
    log_dir: Path = Field(default=ROOT_DIR / "logs")
    export_dir: Path = Field(default=ROOT_DIR / "data" / "exports")
    concurrency: int = Field(default=1, ge=1, le=10)

    browser: BrowserSettings = Field(default_factory=BrowserSettings)
    proxy: ProxySettings = Field(default_factory=ProxySettings)
    retry: RetrySettings = Field(default_factory=RetrySettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)

    @classmethod
    def from_yaml(cls, path: Path) -> "Settings":
        """Load settings from a YAML file, then apply env overrides on top."""
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)


# Singleton — import this everywhere
settings = Settings()
