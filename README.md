<p align="center">
  <img src="docs/images/banner.svg" alt="Food Delivery Scraper Framework" width="800"/>
</p>

Production ready scraping system for GrabFood, ShopeeFood, and GoFood.

## Why this project

This project shows how to build a reliable scraping workflow for food delivery platforms in Southeast Asia.
It is designed for real world constraints such as anti bot protections, dynamic pages, retries, and structured exports.

## Key features

- Multi platform architecture via `ScraperFactory`
- Async scraping with Playwright
- Proxy support with rotation and failure tracking
- Retry strategy with Tenacity
- Structured validation with Pydantic models
- Export to CSV, JSON, and XLSX
- SQLite persistence for sessions and restaurant data
- CLI interface with Typer

## Architecture

```mermaid
flowchart TD
    A[CLI Command] --> B[Scraper Factory]
    B --> C[GrabFood Scraper]
    B --> D[ShopeeFood Scraper]
    B --> E[GoFood Scraper]

    C --> F[Playwright Browser]
    D --> F
    E --> F

    F --> G[Extract and Parse]
    G --> H[Validate Models]
    H --> I[Store to SQLite]
    H --> J[Export CSV JSON XLSX]

    K[Proxy Manager] --> C
    K --> D
    K --> E
```

## Project structure

```text
scraper/
  cli.py
  config.py
  models.py
  core/
    base_scraper.py
    factory.py
  platforms/
    grabfood.py
    shopeefood.py
    gofood.py
  storage/
  exporters/
  utils/

tests/
config/
data/
```

## Quick start

### 1) Create virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3) Optional environment config

```bash
cp .env.example .env
```

If you are on Arch Linux with system Chromium, set:

```bash
export PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium
```

### 4) Run a scrape

```bash
PYTHONPATH=. .venv/bin/python -m scraper.cli scrape \
  --platform grabfood \
  --location jakarta \
  --pages 1 \
  --proxy "http://USERNAME:PASSWORD@HOST:PORT" \
  --log-level INFO
```

### 5) Export from database

```bash
PYTHONPATH=. .venv/bin/python -m scraper.cli export \
  --platform grabfood \
  --city jakarta \
  --format excel
```

## CLI commands

- `scrape` scrape one platform and export result
- `export` export stored data from SQLite
- `stats` show recent scrape sessions

Check full options:

```bash
PYTHONPATH=. .venv/bin/python -m scraper.cli --help
```

## Data output

Typical output columns:

- Platform
- Restaurant ID
- Restaurant Name
- Restaurant URL
- Scraped At

Files are generated in `data/exports/` by default.

## XLSX showcase screenshot

Use this section in your GitHub README preview and project portfolio.

Add your screenshot file to:

`docs/images/xlsx-showcase.png`

Then keep this image block:

![XLSX Showcase](docs/images/xlsx-showcase.png)

Recommended screenshot content:

- Styled header row
- Frozen top row
- Clean column widths
- Filter row enabled

## Reliability notes

- GrabFood URL generation is normalized to avoid duplicated locale paths
- CLI async runner is safe for Python 3.14 event loop behavior
- Proxy authentication is passed correctly to Playwright context

## License

MIT
