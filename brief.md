# 🎯 Best Practices: Showcase Project for SuperFood Hiring Process

## 📋 What SuperFood ACTUALLY Wants to See
Based on the job description, they need someone who can:
1. ✅ Build production scrapers for GoFood/GrabFood/ShopeeFood (domain-specific)
2. ✅ Handle anti-bot systems (CloudFront, WAF, CAPTCHA)
3. ✅ Create reliable data pipelines (not just one-off scripts)
4. ✅ Work independently (freelance → need self-starter)
5. ✅ Deliver clean, documented code (they'll have internal team review)

Your project must prove ALL of these.

---

## 🏗️ Project Structure for MAXIMUM Impact

### Repository Name & Tagline (First Impression)
food-delivery-scraper-framework
"Production-ready scraping for GrabFood, ShopeeFood, and GoFood"
NOT: scraper, web-scraper, my-projects
Why: Specific + professional + keyword-rich for search.

---

### README.md - The Single Most Important File
Structure:
# 🍔 Food Delivery Scraper Framework

> **Production-ready web scraping system for Southeast Asian food delivery platforms**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![Playwright](https://img.shields.io/badge/Playwright-1.40.0-green.svg)](https://playwright.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://docker.com)
[![Tests](https://github.com/yourname/food-delivery-scraper/actions/workflows/tests.yml/badge.svg)](https://github.com/yourname/food-delivery-scraper/actions)

---

## ⚡ **Quick Start (30 seconds)**

bash
git clone https://github.com/yourname/food-delivery-scraper.git
cd food-delivery-scraper
docker-compose up -d  # One command, everything runs

**Output:** `data/exports/restaurants_20240309.csv` with 500+ restaurants

---

## 🎯 **Why This Exists**

Food delivery platforms (GrabFood, ShopeeFood, GoFood) don't provide APIs for competitor analysis. Manual data collection takes **8+ hours per city**. 

This framework automates that process, collecting **500+ restaurants with full menu data in under 15 minutes**, with **98% success rate** even against anti-bot protection.

**Built for:**
- 📊 **Market researchers** analyzing competitor pricing
- 🏪 **Restaurant chains** tracking market presence
- 📈 **Data analysts** building food delivery dashboards
- 🚀 **Startups** like SuperFood building data products

---

## ✨ **Key Features (What Makes This Production-Ready)**

| Feature | Why It Matters | Implementation |
|---------|----------------|----------------|
| **Anti-bot evasion** | Platforms block scrapers | Playwright stealth + proxy rotation + human-like delays |
| **Multi-platform** | GrabFood, ShopeeFood, GoFood | Extensible architecture, add new platform in 200 lines |
| **Data validation** | Bad data = bad decisions | Pydantic models, type hints, schema enforcement |
| **Error resilience** | Scraping fails constantly | Retry logic (exponential backoff), circuit breaker pattern |
| **Monitoring** | Know when it breaks | Structured logs, session metrics, success rate tracking |
| **Dockerized** | Deploy anywhere | Single command setup, no dependency hell |
| **Scalable** | From 10 to 10,000 restaurants | Async scraping, connection pooling, batch processing |
| **Well-documented** | Team handoff possible | 2000+ word README, architecture diagrams, video tutorial |

---

## 📊 **Sample Output (What You Get)**

csv
platform,restaurantid,name,rating,reviewcount,deliverytime,deliveryfee,cuisines,pricerange,url
grabfood,restabc123,Warung Sate Pak Budi,4.5,1243,"25-35 min",15000,"Indonesian,Sate","$$","https://food.grab.com/id/en/restaurant/warung-sate-pak-budi"
shopeefood,restdef456,Sushi Tei,4.2,856,"35-45 min",25000,"Japanese,Sushi","$$$","https://shopee.co.id/food/sushi-tei"

**Full dataset available:** [`data/exports/`](data/exports/)

---

## 🏗️ **Architecture (How It Works)**

mermaid
graph TD
    A[CLI: scraper.cli] --> B[Scraper Factory]
    B --> C[GrabFood Scraper]
    B --> D[ShopeeFood Scraper]
    C --> E[Playwright Browser]
    D --> E
    E --> F[HTML/API Extraction]
    F --> G[Pydantic Validation]
    G --> H[SQLite Storage]
    H --> I[CSV/JSON/Excel Export]
    H --> J[PostgreSQL (optional)]
    
    style E fill:#ff9999
    style G fill:#99ff99
    style H fill:#9999ff

**Design principles:**
- **Separation of concerns**: Each platform in separate module
- **Interface segregation**: Base class defines contract
- **Dependency injection**: Config, storage, proxy manager all injectable
- **Open/closed**: Add new platforms without modifying core

---

## 🔧 **Technical Deep Dive**

### **Tech Stack**

Language: Python 3.11+
Browser Automation: Playwright (async)
Data Validation: Pydantic v2
Storage: SQLite (default) + PostgreSQL support
CLI: Typer (with auto-completion)
Configuration: Pydantic-settings + YAML
Testing: pytest + pytest-asyncio + pytest-cov
Container: Docker + docker-compose
CI/CD: GitHub Actions (tests, lint, type-check)

### **Core Components**

#### **1. Anti-Bot System**
python
# scraper/utils/stealth.py
from playwright.asyncapi import Page

async def applystealth(page: Page):
    """Apply multiple stealth techniques"""
    # Remove webdriver flag
    await page.addinitscript("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        window.chrome = { runtime: {} };
    """)
    
    # Set realistic viewport
    await page.setviewportsize({
        'width': random.randint(1920, 2560),
        'height': random.randint(1080, 1440)
    })
    
    # Random delays between actions
    await page.waitfortimeout(random.randint(1000, 3000))

**Success rate:** 98% on GrabFood (tested 1000+ pages)

#### **2. Proxy Rotation**
python
# scraper/utils/proxymanager.py
class SmartProxyManager:
    """Rotates proxies based on success/failure"""
    
    def init(self, proxylist: List[str]):
        self.proxies = proxylist
        self.failurecount = defaultdict(int)
        self.maxfailures = 3
    
    def getproxy(self) -> Optional[str]:
        """Get least-failed proxy"""
        available = [p for p in self.proxies 
                    if self.failurecount[p] < self.maxfailures]
        if not available:
            return None
        return min(available, key=lambda p: self.failurecount[p])
    
    def marksuccess(self, proxy: str):
        self.failurecount[proxy] = max(0, self.failurecount[proxy] - 1)
    
    def markfailure(self, proxy: str):
        self.failurecount[proxy] += 1

**Tested with:** Smartproxy residential IPs (Indonesia endpoints)

#### **3. Data Validation**
python
# scraper/models.py
from pydantic import BaseModel, Field, validator
from datetime import datetime

class Restaurant(BaseModel):
    platform: Literal["grabfood", "shopeefood", "gofood"]
    restaurantid: str = Field(..., min_length=1)
[3/9/26 10:11 AM] theodores: name: str = Field(..., minlength=1, maxlength=200)
    rating: float = Field(..., ge=0, le=5)
    reviewcount: int = Field(..., ge=0)
    deliverytime: str = Field(..., regex=r'^\d+-\d+ min$')
    deliveryfee: float = Field(..., ge=0)
    cuisines: List[str] = Field(defaultfactory=list)
    scrapedat: datetime = Field(defaultfactory=datetime.now)
    
    @validator('cuisines', pre=True)
    def parsecuisines(cls, v):
        if isinstance(v, str):
            return [c.strip() for c in v.split(',')]
        return v

# Validation ensures:
# - No negative prices
# - Rating between 0-5
# - Delivery time format matches regex
# - Required fields present

#### **4. Error Handling & Retry**
python
# scraper/core/scraper.py
from tenacity import retry, stopafterattempt, waitexponential

class BaseScraper:
    @retry(
        stop=stopafterattempt(3),
        wait=waitexponential(multiplier=1, min=4, max=10),
        beforesleep=lambda retrystate: logger.warning(
            f"Retry {retrystate.attemptnumber} after {retrystate.lastattempt.exception()}"
        )
    )
    async def scrapewithretry(self, url: str):
        """Retry with exponential backoff, circuit breaker pattern"""
        try:
            response = await self.page.goto(url, timeout=30000)
            if response.status == 429:
                raise RateLimitError("Rate limited")
            if response.status == 403:
                raise BlockedError("IP blocked")
            return response
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            raise

---

## 🧪 **Testing Strategy (Proves Quality)**


tests/
├── unit/
│   ├── testmodels.py           # Pydantic validation tests
│   ├── testextractors.py       # HTML parsing with fixtures
│   ├── testproxymanager.py    # Proxy rotation logic
│   └── testvalidators.py       # Data validation edge cases
├── integration/
│   ├── testgrabfoodintegration.py  # Full scrape (mocked)
│   └── teststorage.py          # DB operations
├── fixtures/
│   ├── grabfoodrestaurantpage.html  # Real HTML samples
│   ├── shopeefoodapiresponse.json
│   └── invaliddata.json
└── conftest.py

**Run tests:**
bash
pytest tests/ -v --cov=scraper --cov-report=html

**Coverage:** 85%+ (shown in README badge)

---

## 🐳 **Docker Setup (Deploy Anywhere)**

dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system deps for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright browsers
RUN pip install --no-cache-dir playwright
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy requirements first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Create data directories
RUN mkdir -p data/raw data/processed data/exports logs

CMD ["python", "-m", "scraper.cli", "--help"]

yaml
# docker-compose.yml
version: '3.8'
services:
  scraper:
    build: .
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./config:/app/config:ro
    environment:
      - LOGLEVEL=INFO
      - PYTHONUNBUFFERED=1
    # For proxy support, configure networkmode or add proxy env
    # network_mode: "host"  # if using local proxy

**One-command deployment:**
bash
docker-compose up -d
docker-compose run --rm scraper --platform=grabfood --location=jakarta --pages=5

---

## 📈 **Performance Metrics (Show Results)**

**README section:**
markdown
## 📊 Benchmarks 

## 🚨 **What NOT to Do**

### **❌ DON'T:**
- Don't make it too complex (microservices, Kubernetes) - overkill for freelance
- Don't use paid APIs without mentioning cost
- Don't hide failures - show how you handle them
- Don't claim 100% success rate (unrealistic)
- Don't use pseudocode or TODO comments in README
- Don't have empty test files
- Don't commit API keys/tokens
- Don't ignore rate limits in code examples

### **✅ DO:**
- Do mention **legal considerations** (robots.txt, TOS compliance)
- Do show **real metrics** (success rate, restaurants/hour)
- Do include **setup costs** (proxy costs ~$10-50/month)
- Do mention **maintenance** (sites change, need monitoring)
- Do provide **contact references** (if freelance platform)
- Do show **business value** (time saved, data quality)

---

## 📊 **Comparison: Average vs. SuperFood-Ready Project**

| Aspect | Average Candidate | **Your Project (SuperFood-Ready)** |
|--------|-------------------|-----------------------------------|
| **Scope** | Scrapes one page | Multi-platform framework |
| **Anti-bot** | None or basic | Stealth + proxy + retry |
| **Code Quality** | Script in one file | Modular, typed, tested |
| **Documentation** | 2-line README | 2000+ words + diagrams |
| **Deployment** | Run locally | Dockerized, one command |
| **Testing** | None | 85%+ coverage, CI/CD |
| **Metrics** | "It works" | Success rate, benchmarks |
| **Demo** | None | Video + live demo |
| **Business Value** | Not addressed | Clear ROI (time saved) |

---

## 🎯 **Final Checklist Before Sharing**

### **Repository Must-Haves:**
- [ ] **README.md** with badges, quick start, architecture, benchmarks
- [ ] **LICENSE** (MIT or Apache 2.0)
- [ ] **.gitignore** (Python, VS Code, macOS/Windows, Docker)
- [ ] **requirements.txt** or **pyproject.toml**
- [ ] **Dockerfile** + **docker-compose.yml**
- [ ] **tests/** with at least unit tests
- [ ] **config/** with example YAML
- [ ] **data/examples/** with sample output (CSV/JSON)
- [ ] **docs/** or ARCHITECTURE.md (optional but pro)
- [ ] **Makefile** for common tasks
- [ ] **GitHub Actions** CI (at least lint + test)

### **README Must-Have Sections:**
- [ ] Badges (build, license, Python version)
- [ ] 30-second quick start
- [ ] Problem statement (why this exists)
- [ ] Feature list (with implementation details)
- [ ] Sample output (real CSV snippet)
- [ ] Architecture diagram (Mermaid)
- [ ] Tech stack (with versions)
- [ ] Performance metrics (real numbers)
- [ ] Testing instructions
- [ ] Docker instructions
- [ ] Configuration examples
- [ ] Legal disclaimer (scraping ethics)
- [ ] Contributing guidelines (optional)
- [ ] Demo video embed

### **Code Quality:**
- [ ] Type hints everywhere (`mypy` clean)
- [ ] Docstrings on public functions/classes
- [ ] Logging (not print statements)
- [ ] Error handling (no bare except)
- [ ] Configuration externalized (no hardcoded URLs)
- [ ] Secrets management (use `.env`)
- [ ] No debug code in main branch
- [ ] Consistent formatting (Black/ruff)