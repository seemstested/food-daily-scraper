.DEFAULT_GOAL := help
PYTHON := python3
VENV   := .venv
PIP    := $(VENV)/bin/pip
PY     := $(VENV)/bin/python

# ─────────────────────────────────────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: install
install: $(VENV)/bin/activate  ## Install all dependencies in a virtualenv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(VENV)/bin/playwright install chromium
	@echo "\n✅ Installation complete. Activate: source .venv/bin/activate"

$(VENV)/bin/activate:
	$(PYTHON) -m venv $(VENV)

.PHONY: install-dev
install-dev: install  ## Install dev tools (ruff, mypy, pytest-cov)
	$(PIP) install ruff mypy pytest pytest-asyncio pytest-cov

.PHONY: setup
setup: install  ## Full project setup (install + copy config)
	@cp -n .env.example .env 2>/dev/null || true
	@cp -n config/settings.example.yaml config/settings.yaml 2>/dev/null || true
	@mkdir -p data/raw data/processed data/exports data/examples logs
	@echo "✅ Project setup complete."

# ─────────────────────────────────────────────────────────────────────────────
# Linting & Formatting
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: lint
lint:  ## Run ruff linter
	$(VENV)/bin/ruff check scraper/ tests/

.PHONY: format
format:  ## Auto-format code with ruff
	$(VENV)/bin/ruff format scraper/ tests/
	$(VENV)/bin/ruff check --fix scraper/ tests/

.PHONY: typecheck
typecheck:  ## Run mypy type checker
	$(VENV)/bin/mypy scraper/ --ignore-missing-imports

.PHONY: check
check: lint typecheck  ## Run all static analysis

# ─────────────────────────────────────────────────────────────────────────────
# Testing
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: test
test:  ## Run full test suite with coverage
	$(VENV)/bin/pytest tests/ -v --cov=scraper --cov-report=term-missing --cov-report=html

.PHONY: test-unit
test-unit:  ## Run unit tests only
	$(VENV)/bin/pytest tests/unit/ -v

.PHONY: test-integration
test-integration:  ## Run integration tests only
	$(VENV)/bin/pytest tests/integration/ -v

.PHONY: test-fast
test-fast:  ## Run tests without coverage (faster)
	$(VENV)/bin/pytest tests/ -v -x

# ─────────────────────────────────────────────────────────────────────────────
# Scraping
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: scrape-grabfood
scrape-grabfood:  ## Scrape GrabFood Jakarta (5 pages)
	$(PY) -m scraper.cli scrape --platform grabfood --location jakarta --pages 5

.PHONY: scrape-shopeefood
scrape-shopeefood:  ## Scrape ShopeeFood Jakarta (3 pages)
	$(PY) -m scraper.cli scrape --platform shopeefood --location jakarta --pages 3

.PHONY: scrape-gofood
scrape-gofood:  ## Scrape GoFood Jakarta (3 pages)
	$(PY) -m scraper.cli scrape --platform gofood --location jakarta --pages 3

.PHONY: scrape-all
scrape-all: scrape-grabfood scrape-shopeefood scrape-gofood  ## Scrape all platforms

.PHONY: stats
stats:  ## Show session statistics
	$(PY) -m scraper.cli stats

# ─────────────────────────────────────────────────────────────────────────────
# Docker
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: docker-build
docker-build:  ## Build Docker image
	docker build -t food-delivery-scraper:latest .

.PHONY: docker-run
docker-run:  ## Run scraper in Docker (edit args as needed)
	docker-compose run --rm scrape-task \
	  --platform grabfood --location jakarta --pages 5

.PHONY: docker-test
docker-test:  ## Run tests inside Docker
	docker-compose run --rm --entrypoint pytest scrape-task tests/ -v

.PHONY: docker-clean
docker-clean:  ## Remove containers and volumes
	docker-compose down -v --remove-orphans

# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: clean
clean:  ## Remove build artifacts, caches, coverage reports
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .mypy_cache .ruff_cache .pytest_cache htmlcov .coverage coverage.xml
	@echo "✅ Cleaned."

.PHONY: export-csv
export-csv:  ## Export all stored restaurants to CSV
	$(PY) -m scraper.cli export --format csv

.PHONY: export-excel
export-excel:  ## Export all stored restaurants to Excel
	$(PY) -m scraper.cli export --format excel

.PHONY: help
help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'
