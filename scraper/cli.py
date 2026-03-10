"""
Command-line interface for the food delivery scraper framework.

Usage examples:

    # Scrape GrabFood in Jakarta, 5 pages, export CSV
    python -m scraper.cli scrape --platform grabfood --location jakarta --pages 5

    # Scrape with proxy list
    python -m scraper.cli scrape --platform shopeefood --location surabaya \\
        --proxies proxies.txt --format json

    # Export previously stored data
    python -m scraper.cli export --platform grabfood --city jakarta --format excel

    # Show session stats
    python -m scraper.cli stats
"""

from __future__ import annotations

import asyncio
from concurrent.futures import Future
from datetime import datetime
from pathlib import Path
from threading import Thread
from typing import Any, Coroutine, Optional

import typer
from rich.console import Console
from rich.table import Table

from scraper.config import settings
from scraper.core.factory import ScraperFactory
from scraper.exporters.exporters import CSVExporter, ExcelExporter, JSONExporter
from scraper.storage.sqlite_storage import SQLiteStorage
from scraper.utils.logger import configure_logging, get_logger
from scraper.utils.proxy_manager import ProxyManager

app = typer.Typer(
    name="food-scraper",
    help="Production-ready scraping for GrabFood, ShopeeFood, and GoFood.",
    add_completion=True,
)
console = Console()
logger = get_logger(__name__)


# ── Helper loaders ─────────────────────────────────────────────────────────────

def _load_proxies(path: Optional[Path]) -> list[str]:
    if path is None or not path.exists():
        return []
    proxies = [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    console.print(f"[green]Loaded {len(proxies)} proxies from {path}[/green]")
    return proxies


def _get_exporter(fmt: str, output_dir: Path):
    fmt = fmt.lower()
    if fmt == "csv":
        return CSVExporter(output_dir)
    elif fmt == "json":
        return JSONExporter(output_dir)
    elif fmt in ("excel", "xlsx"):
        return ExcelExporter(output_dir)
    raise typer.BadParameter(f"Unknown format '{fmt}'. Choose: csv, json, excel")


def _run_async(coro: Coroutine[Any, Any, None]) -> None:
    """Run coroutine from CLI in both loop/no-loop environments."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
        return

    result: Future[None] = Future()

    def _runner() -> None:
        try:
            asyncio.run(coro)
        except Exception as exc:
            result.set_exception(exc)
        else:
            result.set_result(None)

    thread = Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()
    result.result()


# ── Commands ───────────────────────────────────────────────────────────────────

@app.command()
def scrape(
    platform: str = typer.Option(
        ..., "--platform", "-p",
        help="Platform to scrape: grabfood | shopeefood | gofood",
    ),
    location: str = typer.Option(
        ..., "--location", "-l",
        help="City slug (e.g. 'jakarta', 'surabaya', 'bali')",
    ),
    pages: int = typer.Option(
        1, "--pages", "-n",
        min=1, max=100,
        help="Number of listing pages to scrape (each yields ~25-30 restaurants)",
    ),
    fmt: str = typer.Option(
        "csv", "--format", "-f",
        help="Export format: csv | json | excel",
    ),
    proxies_file: Optional[Path] = typer.Option(
        None, "--proxies",
        help="Path to newline-delimited proxy list (http://user:pass@host:port)",
        exists=False,
    ),
    proxy: Optional[str] = typer.Option(
        None, "--proxy",
        help="Single proxy URL (http://user:pass@host:port)",
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Output directory (default: data/exports/)",
    ),
    headless: bool = typer.Option(True, "--headless/--no-headless"),
    log_level: str = typer.Option("INFO", "--log-level"),
    save_db: bool = typer.Option(True, "--save-db/--no-save-db", help="Persist to SQLite"),
) -> None:
    """
    Scrape restaurants from a food delivery platform.

    Examples::

        python -m scraper.cli scrape -p grabfood -l jakarta -n 5
        python -m scraper.cli scrape -p gofood -l bali -n 3 --format json
    """
    configure_logging(level=log_level.upper())

    # Apply runtime overrides
    settings.browser.headless = headless
    out_dir = output_dir or settings.export_dir

    proxies = _load_proxies(proxies_file)
    if proxy:
        proxies.append(proxy.strip())

    # de-duplicate while preserving order
    proxies = list(dict.fromkeys([p for p in proxies if p]))

    proxy_manager = (
        ProxyManager(proxies, max_failures=settings.proxy.max_failures)
        if proxies
        else None
    )

    console.print(
        f"\n[bold cyan]🍔 Food Delivery Scraper[/bold cyan]\n"
        f"  Platform : [yellow]{platform}[/yellow]\n"
        f"  Location : [yellow]{location}[/yellow]\n"
        f"  Pages    : [yellow]{pages}[/yellow]\n"
        f"  Proxies  : [yellow]{len(proxies)}[/yellow]\n"
        f"  Output   : [yellow]{fmt.upper()}[/yellow]\n"
    )

    async def _run() -> None:
        async with ScraperFactory.create(
            platform, proxy_manager=proxy_manager
        ) as scraper:
            restaurants = await scraper.scrape(location=location, pages=pages)

            if not restaurants:
                console.print("[red]No restaurants scraped. Check logs.[/red]")
                raise typer.Exit(code=1)

            # Export
            exporter = _get_exporter(fmt, out_dir)
            stem = f"{platform}_{location}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            export_path = exporter.export(restaurants, filename_stem=stem)

            # Persist to DB
            if save_db:
                db = SQLiteStorage(settings.storage.sqlite_path)
                db.upsert_restaurants(restaurants)
                db.save_session(scraper.session)

            # Summary table
            table = Table(title="Scrape Summary", show_header=True)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            table.add_row("Restaurants", str(len(restaurants)))
            table.add_row("Pages processed", str(scraper.session.total_pages))
            table.add_row("Pages failed", str(scraper.session.failed_pages))
            table.add_row("Success rate", f"{scraper.session.success_rate}%")
            table.add_row("Duration", f"{scraper.session.duration_seconds:.1f}s")
            table.add_row("Export path", str(export_path))
            if proxy_manager:
                table.add_row("Proxy rotations", str(scraper.session.proxy_rotations))

            console.print(table)

    _run_async(_run())


@app.command()
def export(
    platform: Optional[str] = typer.Option(None, "--platform", "-p"),
    city: Optional[str] = typer.Option(None, "--city"),
    fmt: str = typer.Option("csv", "--format", "-f"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o"),
) -> None:
    """Export previously stored restaurant data from the database."""
    from scraper.models import Platform as Plat

    configure_logging()
    db = SQLiteStorage(settings.storage.sqlite_path)
    plat = Plat(platform) if platform else None
    restaurants = db.get_restaurants(platform=plat, city=city)

    if not restaurants:
        console.print("[yellow]No matching restaurants in database.[/yellow]")
        raise typer.Exit()

    out_dir = output_dir or settings.export_dir
    exporter = _get_exporter(fmt, out_dir)
    stem = f"export_{platform or 'all'}_{city or 'all'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    path = exporter.export(restaurants, filename_stem=stem)
    console.print(f"[green]Exported {len(restaurants)} restaurants → {path}[/green]")


@app.command()
def stats() -> None:
    """Display session statistics from the database."""
    configure_logging()
    db = SQLiteStorage(settings.storage.sqlite_path)

    with db._conn() as conn:
        conn.row_factory = __import__("sqlite3").Row
        rows = conn.execute(
            "SELECT * FROM scrape_sessions ORDER BY started_at DESC LIMIT 20"
        ).fetchall()

    if not rows:
        console.print("[yellow]No sessions in database yet.[/yellow]")
        return

    table = Table(title="Recent Scrape Sessions", show_header=True)
    for col in ("Session ID", "Platform", "Location", "Restaurants", "Success Rate", "Duration", "Status"):
        table.add_column(col)

    for r in rows:
        total = (r["total_pages"] or 0) + (r["failed_pages"] or 0)
        rate = f"{round(r['total_pages'] / total * 100, 1)}%" if total else "—"
        duration = "—"
        if r["started_at"] and r["finished_at"]:
            start = datetime.fromisoformat(r["started_at"])
            end = datetime.fromisoformat(r["finished_at"])
            duration = f"{(end - start).total_seconds():.0f}s"
        table.add_row(
            r["session_id"],
            r["platform"] or "—",
            r["location"] or "—",
            str(r["total_restaurants"] or 0),
            rate,
            duration,
            r["status"] or "—",
        )

    console.print(table)


# ── Entrypoint ─────────────────────────────────────────────────────────────────

def main():
    app()


if __name__ == "__main__":
    main()
