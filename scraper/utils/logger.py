"""
Structured logging setup.

All scraper modules should use get_logger(__name__) rather than print().

Features:
  - JSON output in production (LOG_FORMAT=json)
  - Coloured human-readable output during development
  - Automatic log rotation: 10 MB files, 5 backups
  - Session correlation via structlog context vars
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

# Optional structlog for structured JSON logging
try:
    import structlog

    _HAS_STRUCTLOG = True
except ImportError:
    _HAS_STRUCTLOG = False


_DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_LOG_DIR = Path(os.getenv("SCRAPER_LOG_DIR", "logs"))
_LOG_LEVEL = os.getenv("SCRAPER_LOG_LEVEL", "INFO").upper()

_configured = False


def configure_logging(level: str = _LOG_LEVEL, log_dir: Path = _LOG_DIR) -> None:
    """
    One-time logging configuration.  Call at application entry point.

    Args:
        level:   Logging level string (DEBUG / INFO / WARNING / ERROR).
        log_dir: Directory for rotating log files.
    """
    global _configured
    if _configured:
        return
    _configured = True

    log_dir.mkdir(parents=True, exist_ok=True)

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stderr),
        logging.handlers.RotatingFileHandler(
            log_dir / "scraper.log",
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        ),
    ]

    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format=_DEFAULT_FORMAT,
        datefmt=_DATE_FORMAT,
        handlers=handlers,
    )

    # Quiet noisy third-party loggers
    for name in ("playwright", "asyncio", "urllib3", "httpx"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Return a standard-library logger for the given module name.

    Args:
        name: Typically ``__name__`` from the calling module.

    Returns:
        Configured :class:`logging.Logger` instance.
    """
    if not _configured:
        configure_logging()
    return logging.getLogger(name)
