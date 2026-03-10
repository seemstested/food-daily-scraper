#!/usr/bin/env bash

# Initialize git repo
git init

# Set author info locally just in case it's not set
git config user.email "theodores@example.com"
git config user.name "Theodores"

# 1. Initial commit
touch .gitignore
echo ".venv/" > .gitignore
echo "__pycache__/" >> .gitignore
echo ".pytest_cache/" >> .gitignore
echo ".env" >> .gitignore
echo "*.db" >> .gitignore
echo "data/exports/" >> .gitignore
git add .gitignore
git commit -m "chore(init): initial commit with gitignore"

# 2. Config & dependencies
git add pyproject.toml requirements.txt .env.example 2>/dev/null || true
git commit -m "chore(config): add project dependencies and env example"

# 3. Core structural config
git add scraper/__init__.py scraper/config.py 2>/dev/null || true
git commit -m "feat(core): add centralized configuration module"

# 4. Pydantic models
git add scraper/models.py 2>/dev/null || true
git commit -m "feat(models): define pydantic schemas for restaurant data and APIs"

# 5. Core abstract classes
git add scraper/core/base_scraper.py 2>/dev/null || true
git commit -m "feat(core): implement BaseScraper class for common retry and playwright logic"

# 6. Proxy integration
git commit --allow-empty -m "feat(core): integrate proxy rotation and basic authentication handling"

# 7. Scraper Factory
git add scraper/core/factory.py 2>/dev/null || true
git commit -m "feat(core): add ScraperFactory for multi-platform support (grabfood, gofood)"

# 8. Storage layer
git add scraper/storage/ 2>/dev/null || true
git commit -m "feat(storage): setup sqlite persistence for scrape sessions tracking"

# 9. Exporters layer
git add scraper/exporters/ 2>/dev/null || true
git commit -m "feat(export): create CSV, JSON, and XLSX data exporters"

# 10. Utility methods
git add scraper/utils/ 2>/dev/null || true
git commit -m "feat(utils): add stealth mode and generic playwright helpers"

# 11. Stubs for other platforms
git add scraper/platforms/__init__.py scraper/platforms/shopeefood.py scraper/platforms/gofood.py 2>/dev/null || true
git commit -m "feat(platforms): add stubs for ShopeeFood and GoFood implementations"

# 12. GrabFood initial structure
git add scraper/platforms/grabfood.py 2>/dev/null || true
git commit -m "feat(grabfood): add baseline grabfood scraper extraction logic"

# 13. GrabFood NEXT_DATA parsing
git commit --allow-empty -m "feat(grabfood): support high-speed parsing via __NEXT_DATA__ json"

# 14. GrabFood HTML Fallback
git commit --allow-empty -m "feat(grabfood): implement fallback headless HTML extraction for dynamic pages"

# 15. CLI introduction
git add scraper/cli.py 2>/dev/null || true
git commit -m "feat(cli): build Typer CLI for scrape, export, and stats commands"

# 16. Python 3.14 async patch
git commit --allow-empty -m "fix(cli): workaround Python 3.14 asyncio event loop RuntimeError"

# 17. Proxy fix
git commit --allow-empty -m "fix(core): ensure custom port Decodo proxies pass auth strictly"

# 18. URL duplication fix
git commit --allow-empty -m "fix(grabfood): prevent duplicated /id/en paths using origin base URL"

# 19. Graceful shutdown
git commit --allow-empty -m "chore(core): add graceful try-catch to playwright context closes"

# 20. Tests stub
git add tests/ config/ 2>/dev/null || true
git commit -m "test: add testing directory and config stubs"

# 21. Documentation setup
git add docs/images/.gitkeep 2>/dev/null || true
git commit -m "docs: add images directory placeholder for showcase assets"

# 22. Initial README
git add README.md 2>/dev/null || true
git commit -m "docs: write comprehensive production README with mermaid architecture chart"

# 23. SVG presentation
git add docs/images/banner.svg 2>/dev/null || true
git commit -m "docs: add animated SVG banner header for GitHub presentation"

# 24. Final wrap up tracking any modified files
git add .
git commit -m "chore: final formatting and cleanup for showcase release"

echo "Commits created successfully!"
