<div align="center">

# 🍜 Food Delivery Scraper

**Production-grade data extraction engine for Indonesia's big-3 food delivery platforms**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-1.42-2EAD33?style=flat-square&logo=playwright&logoColor=white)](https://playwright.dev/python/)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?style=flat-square&logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![CI](https://img.shields.io/github/actions/workflow/status/yourusername/food-delivery-scraper/ci.yml?branch=main&label=CI&style=flat-square&logo=github)](https://github.com/yourusername/food-delivery-scraper/actions)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker&logoColor=white)](./Dockerfile)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000?style=flat-square&logo=ruff)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](./LICENSE)

Extracts **restaurants, ratings, delivery windows, menus, promotions & geo-coordinates** from  
**GrabFood · GoFood · ShopeeFood** — with a 3-layer extraction pipeline, stealth anti-bot bypass,  
smart proxy rotation, Pydantic-validated models, and multi-format export. Built for scale.

[Quick Start](#-quick-start) · [Architecture](#-architecture) · [CLI Usage](#-cli-reference) · [Data Schema](#-data-schema) · [Docker](#-docker-deployment)

</div>

---

## 🎯 The Problem

Food-tech platforms make critical decisions — pricing, restaurant partnerships, market expansion — on fragmented, often stale data. Manually monitoring hundreds of restaurant listings across GrabFood, GoFood, and ShopeeFood is operationally impossible at any meaningful scale.

**This engine automates that entire process** — structured, validated, versioned data from three platforms, one CLI command.

---

## ⚡ At a Glance

| Capability                     | Detail                                                                  |
| ------------------------------ | ----------------------------------------------------------------------- |
| **Platforms**                  | GrabFood · GoFood · ShopeeFood                                          |
| **Data points per restaurant** | 25+ fields (rating, delivery time, fee, cuisines, geo, promos, menu)    |
| **Throughput**                 | ~25–30 restaurants per listing page                                     |
| **Extraction strategy**        | 3-layer pipeline: SSR JSON → XHR interception → DOM fallback            |
| **Anti-bot**                   | 8-patch JS stealth layer + gaussian human delays + randomised viewports |
| **Proxy rotation**             | 3 strategies, failure-aware, forgiveness mechanism, thread-safe         |
| **Retry logic**                | Exponential backoff via `tenacity`, per-exception type                  |
| **Export formats**             | CSV · JSON · Excel (XLSX)                                               |
| **Persistence**                | SQLite (WAL mode, upsert semantics) · PostgreSQL-ready                  |
| **Observability**              | Structured JSON logging · session audit trail · per-proxy health stats  |
| **Deployment**                 | Multi-stage Docker build · GitHub Actions CI                            |

---

## ✨ Feature Highlights

### 🕵️ Anti-Bot Evasion — Stealth by Design

Eight JavaScript patches are injected into every page context before any navigation:
removes the `webdriver` fingerprint, spoofs `navigator.plugins` with three realistic Chrome entries, fakes `navigator.languages`, injects a `window.chrome` runtime stub, patches `Notification.permission`, and spoofs `deviceMemory` / `hardwareConcurrency`. Paired with randomised desktop viewports (5 resolutions), Gaussian-sampled delays, ease-in-out human scroll curves, and Jakarta geolocation / timezone headers.

### 🔄 3-Layer Extraction Pipeline (GrabFood)

Platform scraping degrades gracefully through three strategies so a single page redesign never causes a total failure:

1. **`__NEXT_DATA__` SSR JSON** — parses the Next.js server-side rendered JSON blob embedded in the page (fastest, most resilient to DOM changes)
2. **XHR / API Interception** — captures in-flight `merchantService` REST responses before the page finishes rendering
3. **DOM Fallback** — structured CSS-selector scraping of rendered restaurant cards

### 🌐 Multi-Platform Support

Each platform has bespoke extraction logic that accounts for its unique stack:

- **GrabFood** — CloudFront WAF + Next.js SSR + internal REST API
- **GoFood** — AWS WAF + single-page app + Bearer token from `localStorage`
- **ShopeeFood** — CloudFlare protection + React SPA + lazy-loaded API payloads

### 🔁 Smart Proxy Rotation

Thread-safe `ProxyManager` with three configurable strategies (`least_failed` · `round_robin` · `random`). Failed proxies are tracked per-request; successful requests apply a forgiveness credit. Proxies exceeding a configurable failure threshold are automatically retired, and full health stats are available at any time.

### ✅ Strict Data Validation

Every scraped record passes through a **Pydantic v2** `Restaurant` model before it touches storage or export. Field-level validators enforce ranges (rating `0–5`, lat/lon bounds), type coercion, delivery time ordering, and discount logic. Invalid records are logged and skipped — never silently persisted.

### 📊 Multi-Format Export

Identical `BaseExporter` interface for CSV, JSON, and Excel (XLSX). The Excel exporter auto-sizes columns and applies styled blue headers out of the box — ready to share with non-technical stakeholders.

---

## 🏗️ Architecture

```mermaid
flowchart TD
    CLI["🖥️  CLI  /  Python API"] --> Factory["ScraperFactory"]

    Factory -->|"grabfood"| GF["GrabFoodScraper"]
    Factory -->|"gofood"| GOF["GoFoodScraper"]
    Factory -->|"shopeefood"| SF["ShopeeFoodScraper"]

    GF & GOF & SF --> Base["BaseScraper (ABC)"]

    Base --> PM["ProxyManager\nleast_failed · round_robin · random"]
    Base --> SL["Stealth Layer\n8 JS patches · human delays · random viewport"]
    Base --> RB["Retry + Backoff\ntenacity · per-exception strategy"]

    subgraph "Extraction Pipeline (per page)"
        direction TB
        L1["① __NEXT_DATA__ SSR JSON"]
        L2["② XHR / API Interception"]
        L3["③ DOM Fallback"]
        L1 -->|not found| L2
        L2 -->|not found| L3
    end

    Base -->|"scrape_listing_page(url)"| L1

    L3 --> PV["Pydantic v2\nValidation + Coercion"]
    PV --> DB["SQLiteStorage\nWAL · Upsert · Indexed"]
    PV --> EX["Exporters"]
    EX --> CSV["CSV"]
    EX --> JSON["JSON"]
    EX --> XLS["Excel .xlsx"]

    DB --> SS["ScrapeSession\nAudit Trail"]
```

### Key Design Decisions

| Decision                   | Rationale                                                                                                                                                                                                    |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Abstract `BaseScraper`** | Enforces a uniform scrape lifecycle (launch → navigate → extract → validate → store) across all platforms. Adding a 4th platform requires only `build_listing_urls()` and `scrape_listing_page()` overrides. |
| **Factory pattern**        | Decouples the caller from concrete scraper classes. Platform is resolved by enum — `ConfigurationError` is raised on unknown slugs, never a silent `None`.                                                   |
| **`tenacity` for retry**   | Per-exception retry conditions: `NetworkError` and `EmptyResponseError` are retried; `BlockedError` and `CaptchaError` immediately trigger proxy rotation and re-raise.                                      |
| **Pydantic v2 for models** | Zero-tolerance for dirty data in the pipeline. Scraping 500 restaurants and getting 12 malformed records silently is worse than getting an explicit count of skipped rows.                                   |
| **SQLite with WAL mode**   | Portable, zero-infrastructure default for local and containerised runs. The `upsert` semantics mean re-scraping a city simply refreshes stale rows without duplicates.                                       |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- (Optional) [Docker](https://docs.docker.com/get-docker/)

### 1 — Install

```bash
git clone https://github.com/yourusername/food-delivery-scraper.git
cd food-delivery-scraper

python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 2 — Configure (optional)

```bash
cp config/settings.example.yaml config/settings.yaml
# Edit config/settings.yaml — or skip this step to use sensible defaults
```

### 3 — First Scrape

```bash
# Scrape GrabFood · Jakarta · 5 pages → CSV
python -m scraper.cli scrape \
  --platform grabfood \
  --location jakarta \
  --pages 5 \
  --format csv
```

```
🍔 Food Delivery Scraper
  Platform : grabfood
  Location : jakarta
  Pages    : 5
  Proxies  : 0
  Output   : CSV

  ┌──────────────────────┬──────────────────────────────────────────┐
  │ Metric               │ Value                                    │
  ├──────────────────────┼──────────────────────────────────────────┤
  │ Restaurants          │ 147                                      │
  │ Pages processed      │ 5                                        │
  │ Pages failed         │ 0                                        │
  │ Success rate         │ 100.0%                                   │
  │ Duration             │ 94.3s                                    │
  │ Export path          │ data/exports/grabfood_jakarta_20250615…  │
  └──────────────────────┴──────────────────────────────────────────┘
```

### 4 — Scrape with Proxy

```bash
# Using Decodo / any residential proxy pool
python -m scraper.cli scrape \
  --platform shopeefood \
  --location surabaya \
  --pages 3 \
  --proxy "http://user:pass@gate.decodo.com:7777" \
  --format json
```

---

## 🖥️ CLI Reference

### `scrape` — Extract restaurant listings

```
python -m scraper.cli scrape [OPTIONS]
```

| Option                       | Type   | Default         | Description                                       |
| ---------------------------- | ------ | --------------- | ------------------------------------------------- |
| `--platform`, `-p`           | `str`  | **required**    | `grabfood` · `gofood` · `shopeefood`              |
| `--location`, `-l`           | `str`  | **required**    | City slug: `jakarta`, `surabaya`, `bali`, etc.    |
| `--pages`, `-n`              | `int`  | `1`             | Listing pages to scrape (≈25–30 restaurants each) |
| `--format`, `-f`             | `str`  | `csv`           | `csv` · `json` · `excel`                          |
| `--proxies`                  | `Path` | —               | Newline-delimited proxy list file                 |
| `--proxy`                    | `str`  | —               | Single proxy URL                                  |
| `--output`, `-o`             | `Path` | `data/exports/` | Output directory                                  |
| `--headless / --no-headless` | `bool` | `true`          | Toggle visible browser (debug mode)               |
| `--log-level`                | `str`  | `INFO`          | `DEBUG` · `INFO` · `WARNING` · `ERROR`            |
| `--save-db / --no-save-db`   | `bool` | `true`          | Persist results to SQLite                         |

**Examples:**

```bash
# GoFood · Bali · 3 pages · JSON output
python -m scraper.cli scrape -p gofood -l bali -n 3 -f json

# GrabFood with proxy file · debug mode · no DB
python -m scraper.cli scrape -p grabfood -l jakarta -n 10 \
  --proxies proxies.txt \
  --no-headless \
  --no-save-db

# ShopeeFood · full run with logging
python -m scraper.cli scrape -p shopeefood -l bandung -n 5 \
  --format excel \
  --log-level DEBUG
```

---

### `export` — Re-export data from the database

```bash
# All GoFood restaurants in Jakarta → Excel
python -m scraper.cli export --platform gofood --city jakarta --format excel

# All platforms, all cities → CSV
python -m scraper.cli export --format csv
```

---

### `stats` — Inspect session history

```bash
python -m scraper.cli stats
```

```
          Recent Scrape Sessions
┌────────────┬────────────┬──────────┬─────────────┬──────────────┬──────────┬───────────┐
│ Session ID │ Platform   │ Location │ Restaurants │ Success Rate │ Duration │ Status    │
├────────────┼────────────┼──────────┼─────────────┼──────────────┼──────────┼───────────┤
│ a1b2c3d4   │ grabfood   │ jakarta  │ 147         │ 100.0%       │ 94s      │ completed │
│ e5f6g7h8   │ gofood     │ bali     │ 89          │ 100.0%       │ 71s      │ completed │
│ i9j0k1l2   │ shopeefood │ surabaya │ 112         │ 95.2%        │ 88s      │ completed │
└────────────┴────────────┴──────────┴─────────────┴──────────────┴──────────┴───────────┘
```

---

### Python API

```python
import asyncio
from scraper.core.factory import ScraperFactory
from scraper.utils.proxy_manager import ProxyManager

async def main():
    proxies = ["http://user:pass@proxy1:8080", "http://user:pass@proxy2:8080"]
    pm = ProxyManager(proxies, max_failures=3, strategy="least_failed")

    async with ScraperFactory.create("grabfood", proxy_manager=pm) as scraper:
        restaurants = await scraper.scrape(location="jakarta", pages=5)

    for r in restaurants:
        print(f"{r.name:40s}  ⭐ {r.rating}  🛵 {r.delivery_time_str}  📍 {r.city}")

asyncio.run(main())
```

---

## 📊 Data Schema

Every scraped record is validated through the `Restaurant` Pydantic model before it enters storage or export.

### `Restaurant` model

| Field               | Type                  | Description                               |
| ------------------- | --------------------- | ----------------------------------------- |
| `platform`          | `Platform`            | `grabfood` · `gofood` · `shopeefood`      |
| `restaurant_id`     | `str`                 | Platform-native unique identifier         |
| `name`              | `str`                 | Display name (stripped, max 300 chars)    |
| `slug`              | `str \| None`         | URL-friendly identifier                   |
| `rating`            | `float \| None`       | 0–5 scale, `None` if not yet rated        |
| `review_count`      | `int \| None`         | Total number of reviews                   |
| `delivery_time_min` | `int \| None`         | Minimum estimated delivery (minutes)      |
| `delivery_time_max` | `int \| None`         | Maximum estimated delivery (minutes)      |
| `delivery_fee`      | `float \| None`       | In IDR                                    |
| `minimum_order`     | `float \| None`       | In IDR                                    |
| `cuisines`          | `list[str]`           | e.g. `["Indonesian", "Rice Bowl"]`        |
| `price_range`       | `$ / $$ / $$$ / $$$$` | Budget to luxury classification           |
| `tags`              | `list[str]`           | Platform promotional tags                 |
| `city`              | `str \| None`         | City name                                 |
| `district`          | `str \| None`         | Sub-city district                         |
| `address`           | `str \| None`         | Full street address                       |
| `latitude`          | `float \| None`       | WGS84 (-90 to 90)                         |
| `longitude`         | `float \| None`       | WGS84 (-180 to 180)                       |
| `is_open`           | `bool \| None`        | Current open/closed status                |
| `is_promoted`       | `bool`                | Whether currently running an ad           |
| `promo_label`       | `str \| None`         | Promotion text (e.g. "50% off delivery")  |
| `menu_items`        | `list[MenuItem]`      | Nested menu items when available          |
| `url`               | `str`                 | Direct restaurant page link               |
| `scraped_at`        | `datetime`            | UTC timestamp of extraction               |
| `scrape_session_id` | `str \| None`         | Links record to `ScrapeSession` audit row |

### `MenuItem` sub-model

| Field            | Type            | Description                              |
| ---------------- | --------------- | ---------------------------------------- |
| `item_id`        | `str`           | Platform-native item ID                  |
| `name`           | `str`           | Menu item name                           |
| `description`    | `str \| None`   | Item description                         |
| `price`          | `float`         | Current price in IDR                     |
| `original_price` | `float \| None` | Pre-discount price (validated ≥ `price`) |
| `is_available`   | `bool`          | In-stock status                          |
| `category`       | `str \| None`   | Menu category / section                  |

---

## 🛡️ Anti-Bot Evasion

The stealth layer applies 8 JavaScript patches via Playwright's `addInitScript` — injected before any page code runs, making detection virtually impossible without a dedicated fingerprinting service:

```
┌───┬──────────────────────────────┬─────────────────────────────────────────────────────┐
│ # │ Patch                        │ What it does                                        │
├───┼──────────────────────────────┼─────────────────────────────────────────────────────┤
│ 1 │ navigator.webdriver removal  │ Deletes the flag automation frameworks set by default│
│ 2 │ navigator.plugins spoof      │ Injects 3 realistic Chrome plugin entries           │
│ 3 │ navigator.languages spoof    │ Returns ['en-US', 'en', 'id'] — IDN locale mix      │
│ 4 │ window.chrome runtime stub   │ Simulates Chrome's native runtime object            │
│ 5 │ Notification.permission      │ Returns 'default' instead of automation's 'denied'  │
│ 6 │ navigator.deviceMemory       │ Reports 8 GB (common mid-range device)              │
│ 7 │ navigator.hardwareConcurrency│ Reports 8 cores                                     │
│ 8 │ permissions.query patch      │ Routes notification queries through spoofed state   │
└───┴──────────────────────────────┴─────────────────────────────────────────────────────┘
```

**Additional behavioural mitigations:**

- **Gaussian delay sampling** — wait times are sampled from a truncated normal distribution (not uniform random), producing natural clustering around the mean rather than flat-probability spikes
- **Ease-in-out human scroll** — scroll steps follow a cosine curve to mimic real deceleration and acceleration
- **Randomised viewport** — one of five realistic desktop resolutions (1366×768 to 2560×1440) per session
- **Jakarta geolocation + timezone** — `Asia/Jakarta`, `(-6.2088, 106.8456)`, `Accept-Language: en-US,en;q=0.9,id;q=0.8`
- **`--disable-blink-features=AutomationControlled`** — browser launch arg that prevents Blink from exposing automation mode

---

## 🔁 Proxy Management

```python
from scraper.utils.proxy_manager import ProxyManager

pm = ProxyManager(
    proxies=["http://user:pass@host1:port", "http://user:pass@host2:port"],
    max_failures=3,          # burn threshold
    strategy="least_failed", # rotation algorithm
)

proxy = pm.get_proxy()    # select next proxy
pm.mark_success(proxy)    # failure count -1 (forgiveness)
pm.mark_failure(proxy)    # failure count +1

print(pm.stats())         # per-proxy health breakdown
# [{'proxy': '...', 'failures': 0, 'successes': 12, 'healthy': True}, ...]
```

| Strategy                   | Behaviour                                                         | Best for                                      |
| -------------------------- | ----------------------------------------------------------------- | --------------------------------------------- |
| `least_failed` _(default)_ | Always selects the proxy with the lowest cumulative failure count | Long-running jobs where proxy health diverges |
| `round_robin`              | Cycles through healthy proxies sequentially                       | Even load distribution across a fresh pool    |
| `random`                   | Uniform random selection from healthy proxies                     | Avoiding predictable access patterns          |

**Forgiveness mechanism:** a successful request decrements the failure counter by 1, allowing a temporarily throttled proxy to recover over time rather than being permanently retired after a transient block.

---

## ⚙️ Configuration

Configuration is resolved in priority order: **environment variables → `config/settings.yaml` → built-in defaults**.

```bash
cp config/settings.example.yaml config/settings.yaml
```

```yaml
# config/settings.yaml
log_level: INFO # DEBUG | INFO | WARNING | ERROR
concurrency: 1 # parallel scraper instances (increase carefully)

browser:
  headless: true
  timeout_ms: 30000
  slow_mo: 0 # ms between Playwright actions (0 = full speed)

proxy:
  enabled: false
  max_failures: 3
  rotation_strategy: least_failed # least_failed | round_robin | random

retry:
  max_attempts: 3
  wait_min: 4.0 # seconds
  wait_max: 10.0
  multiplier: 1.5 # exponential backoff factor

storage:
  backend: sqlite # sqlite | postgres
  sqlite_path: data/scraper.db
  save_raw_html: true # archive page HTML for replay/debugging

rate_limit:
  min_delay_ms: 1500
  max_delay_ms: 4000
  page_delay_ms: 3000 # extra pause between pagination requests
```

Every setting is also accessible via environment variable with the `SCRAPER_` prefix:

```bash
SCRAPER_BROWSER_HEADLESS=false
SCRAPER_PROXY_PROXIES="http://user:pass@host1:8080,http://user:pass@host2:8080"
SCRAPER_RETRY_MAX_ATTEMPTS=5
SCRAPER_STORAGE_BACKEND=postgres
SCRAPER_STORAGE_POSTGRES_DSN="postgresql://user:pass@localhost:5432/scraper"
```

---

## 🐳 Docker Deployment

The image uses a **multi-stage build** to separate the wheel-building environment from the lean runtime. The final image runs as a non-root `scraper` user.

```bash
# Build
docker build -t food-delivery-scraper:latest .

# Single scrape
docker run --rm \
  -v $(pwd)/data:/app/data \
  -e SCRAPER_PROXY_PROXIES="http://user:pass@host:port" \
  food-delivery-scraper:latest \
  python -m scraper.cli scrape --platform grabfood --location jakarta --pages 5

# Docker Compose (persistent volume + env file)
docker compose up
```

```yaml
# docker-compose.yml excerpt
services:
  scraper:
    build: .
    volumes:
      - ./data:/app/data
      - ./config:/app/config
      - ./logs:/app/logs
    env_file: .env
```

> **Healthcheck:** the container self-validates on startup — `python -c "from scraper.cli import app; print('OK')"` — so orchestrators like ECS or Kubernetes can detect broken images before they serve traffic.

---

## 🧪 Tests & CI

```bash
# Full test suite
pytest tests/ -v --cov=scraper --cov-report=term-missing

# Lint + format check
ruff check . && ruff format --check .

# Type checking
mypy scraper/ --ignore-missing-imports
```

The GitHub Actions pipeline runs on every push to `main` / `develop` and every pull request:

```
CI Pipeline
├── 🔍 Lint & Type Check  →  ruff (lint + format) · mypy
├── 🧪 Tests              →  pytest on Python 3.11 + 3.12
│                            coverage report → Codecov
├── 🐳 Docker Build       →  validates multi-stage Dockerfile (runs after lint + tests)
└── 🔒 Security Scan      →  pip-audit on requirements.txt
```

---

## 📁 Project Structure

```
food-delivery-scraper/
├── .github/
│   └── workflows/
│       └── ci.yml              # Lint · Tests · Docker Build · Security Scan
├── config/
│   └── settings.example.yaml  # Fully annotated config template
├── data/
│   ├── exports/                # CSV / JSON / XLSX output files
│   └── raw/                    # Archived raw HTML (debug / replay)
├── docs/
│   └── images/                 # README assets
├── logs/                       # Structured JSON log files
├── scraper/
│   ├── core/
│   │   ├── base_scraper.py     # Abstract base: lifecycle, retry, stealth, proxy
│   │   └── factory.py          # Platform → scraper class resolver
│   ├── platforms/
│   │   ├── grabfood.py         # CloudFront WAF · Next.js SSR · tri-layer extraction
│   │   ├── gofood.py           # AWS WAF · SPA · Bearer token interception
│   │   └── shopeefood.py       # CloudFlare · React · lazy-load API capture
│   ├── exporters/
│   │   └── exporters.py        # CSV · JSON · Excel (XLSX) with styled headers
│   ├── storage/
│   │   └── sqlite_storage.py   # WAL-mode SQLite · upsert · indexed queries
│   ├── utils/
│   │   ├── logger.py           # Structured JSON logging
│   │   ├── proxy_manager.py    # Thread-safe rotation · forgiveness · health stats
│   │   └── stealth.py          # 8 JS patches · gaussian delays · human scroll
│   ├── cli.py                  # Typer CLI: scrape · export · stats
│   ├── config.py               # Pydantic-Settings: env vars → YAML → defaults
│   ├── exceptions.py           # Fine-grained exception hierarchy (15 types)
│   └── models.py               # Pydantic v2: Restaurant · MenuItem · ScrapeSession
├── tests/
│   ├── fixtures/               # Shared test data
│   ├── integration/            # End-to-end scrape tests
│   └── unit/                   # Per-module unit tests
├── Dockerfile                  # Multi-stage build (builder + runtime, non-root user)
├── docker-compose.yml
├── Makefile
├── pyproject.toml
└── requirements.txt
```

---

## 🛠️ Tech Stack

| Layer                  | Library                                                                                             | Purpose                                                       |
| ---------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| **Browser automation** | [Playwright](https://playwright.dev/python/) `1.42`                                                 | Async Chromium control, network interception, JS evaluation   |
| **Anti-bot stealth**   | Custom (`utils/stealth.py`)                                                                         | JS injection, behavioural simulation                          |
| **Retry logic**        | [tenacity](https://github.com/jd/tenacity) `8.2`                                                    | Declarative exponential backoff with per-exception conditions |
| **Data validation**    | [Pydantic v2](https://docs.pydantic.dev/) `2.6`                                                     | Strict model validation, serialisation, flat dict export      |
| **CLI**                | [Typer](https://typer.tiangolo.com/) + [Rich](https://github.com/Textualize/rich)                   | Auto-generated `--help`, styled terminal tables               |
| **Configuration**      | [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)                   | Layered config: env vars → YAML → defaults                    |
| **Storage**            | SQLite (`sqlite3` stdlib)                                                                           | WAL mode, upsert semantics, zero-infrastructure               |
| **HTTP**               | [httpx](https://www.python-httpx.org/) `0.27`                                                       | Async HTTP for direct API calls where Playwright isn't needed |
| **Excel export**       | [openpyxl](https://openpyxl.readthedocs.io/) `3.1`                                                  | XLSX generation with styled headers and auto-sized columns    |
| **Linting**            | [ruff](https://github.com/astral-sh/ruff) `0.3`                                                     | Lint + format in one tool, replaces flake8 + isort + black    |
| **Type checking**      | [mypy](https://mypy.readthedocs.io/) `1.9`                                                          | Static analysis across the entire package                     |
| **Testing**            | [pytest](https://docs.pytest.org/) + [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio) | Async test support, coverage reporting                        |
| **CI/CD**              | GitHub Actions                                                                                      | Lint · Tests (3.11 + 3.12) · Docker · pip-audit               |
| **Containerisation**   | Docker (multi-stage)                                                                                | Lean runtime image, non-root user, healthcheck                |

---

## 📄 License

Distributed under the MIT License. See [`LICENSE`](./LICENSE) for details.

---

<div align="center">

Built with precision for the food-tech data ecosystem. 🍱

</div>
