# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps needed for building wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip wheel --no-deps --wheel-dir /wheels -r requirements.txt


# ── Stage 2: runtime image ─────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="your-email@example.com" \
      description="Food Delivery Scraper Framework" \
      version="1.0.0"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# System dependencies for Playwright / Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libgdk-pixbuf2.0-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Install pre-built wheels from builder stage
COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels /wheels/* \
 && rm -rf /wheels

# Install Playwright browsers (Chromium only — smallest footprint)
RUN playwright install chromium \
 && playwright install-deps chromium

# Non-root user for security
RUN useradd --create-home --shell /bin/bash scraper
USER scraper

# Copy source (respect .dockerignore)
COPY --chown=scraper:scraper . .

# Create required directories
RUN mkdir -p data/raw data/processed data/exports logs

# Healthcheck — verify the CLI is importable
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "from scraper.cli import app; print('OK')" || exit 1

CMD ["python", "-m", "scraper.cli", "--help"]
