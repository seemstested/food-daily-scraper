"""
Custom exception hierarchy for the scraper framework.
Fine-grained exceptions allow callers to handle different failure modes precisely.
"""


class ScraperBaseError(Exception):
    """Root exception for all scraper errors."""


# ── Network / HTTP ─────────────────────────────────────────────────────────────

class NetworkError(ScraperBaseError):
    """General network-level failure (timeout, connection refused, etc.)."""


class RateLimitError(ScraperBaseError):
    """HTTP 429 — the platform is throttling our requests."""

    def __init__(self, retry_after: int = 60) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Suggested retry after {retry_after}s.")


class BlockedError(ScraperBaseError):
    """HTTP 403 / CAPTCHA — the IP or session has been blocked."""


class CaptchaError(BlockedError):
    """A CAPTCHA challenge was encountered."""


# ── Anti-bot / Session ────────────────────────────────────────────────────────

class SessionExpiredError(ScraperBaseError):
    """The browser session or auth token has expired and must be renewed."""


class StealthFailureError(ScraperBaseError):
    """Anti-bot stealth measures failed to bypass detection."""


# ── Parsing / Data ────────────────────────────────────────────────────────────

class ParseError(ScraperBaseError):
    """Could not extract expected data from the page/response."""

    def __init__(self, field: str, url: str = "") -> None:
        self.field = field
        self.url = url
        super().__init__(f"Failed to parse '{field}' from {url!r}")


class ValidationError(ScraperBaseError):
    """Extracted data failed Pydantic model validation."""


class EmptyResponseError(ScraperBaseError):
    """Page loaded but returned no usable data (possible soft-block)."""


# ── Proxy ─────────────────────────────────────────────────────────────────────

class ProxyError(ScraperBaseError):
    """Proxy connection or authentication failure."""


class NoProxyAvailableError(ProxyError):
    """All known proxies have exceeded their failure threshold."""


# ── Storage ───────────────────────────────────────────────────────────────────

class StorageError(ScraperBaseError):
    """Database or filesystem persistence failure."""


# ── Configuration ─────────────────────────────────────────────────────────────

class ConfigurationError(ScraperBaseError):
    """Invalid or missing configuration."""
