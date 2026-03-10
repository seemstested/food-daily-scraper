"""
Smart proxy manager with failure-aware rotation.

Strategies:
  * least_failed  — always prefer the proxy with the lowest failure count
  * round_robin   — cycle through proxies sequentially
  * random        — uniform random selection from healthy proxies

A proxy is considered "burned" when its failure count exceeds max_failures.
A successful request reduces the failure count by 1 (forgiveness mechanism).
"""

from __future__ import annotations

import random
import threading
from collections import defaultdict
from itertools import cycle
from typing import Dict, List, Optional

from scraper.exceptions import NoProxyAvailableError
from scraper.utils.logger import get_logger

logger = get_logger(__name__)


class ProxyManager:
    """
    Thread-safe proxy pool with health-based rotation.

    Args:
        proxies:       List of proxy URLs (e.g. "http://user:pass@host:port").
        max_failures:  Failure threshold before a proxy is deemed unusable.
        strategy:      Rotation strategy — 'least_failed', 'round_robin', 'random'.
    """

    def __init__(
        self,
        proxies: List[str],
        max_failures: int = 3,
        strategy: str = "least_failed",
    ) -> None:
        self._proxies = list(proxies)
        self.max_failures = max_failures
        self.strategy = strategy
        self._failure_count: Dict[str, int] = defaultdict(int)
        self._success_count: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()
        self._rr_cycle = cycle(self._proxies) if self._proxies else iter([])
        logger.info(
            "ProxyManager initialised",
            extra={"proxy_count": len(self._proxies), "strategy": strategy},
        )

    # ── Public interface ───────────────────────────────────────────────────────

    def get_proxy(self) -> Optional[str]:
        """
        Return the next proxy to use, or None if no proxies are configured.

        Raises:
            NoProxyAvailableError: All proxies have exceeded max_failures.
        """
        if not self._proxies:
            return None

        with self._lock:
            healthy = self._healthy()
            if not healthy:
                raise NoProxyAvailableError(
                    f"All {len(self._proxies)} proxies exceeded failure threshold "
                    f"({self.max_failures})."
                )

            if self.strategy == "round_robin":
                proxy = self._round_robin(healthy)
            elif self.strategy == "random":
                proxy = random.choice(healthy)
            else:  # least_failed (default)
                proxy = min(healthy, key=lambda p: self._failure_count[p])

        logger.debug("Selected proxy %s", proxy)
        return proxy

    def mark_success(self, proxy: str) -> None:
        """Reduce failure count on success (forgiveness)."""
        with self._lock:
            self._failure_count[proxy] = max(0, self._failure_count[proxy] - 1)
            self._success_count[proxy] += 1
        logger.debug("Proxy success: %s (failures=%d)", proxy, self._failure_count[proxy])

    def mark_failure(self, proxy: str) -> None:
        """Increment failure count for proxy."""
        with self._lock:
            self._failure_count[proxy] += 1
        count = self._failure_count[proxy]
        if count >= self.max_failures:
            logger.warning("Proxy burned (failures=%d): %s", count, proxy)
        else:
            logger.debug("Proxy failure %d/%d: %s", count, self.max_failures, proxy)

    def reset(self, proxy: Optional[str] = None) -> None:
        """Reset failure counts — all proxies or a specific one."""
        with self._lock:
            if proxy:
                self._failure_count[proxy] = 0
            else:
                self._failure_count.clear()
        logger.info("Proxy failure counts reset (%s)", proxy or "all")

    # ── Status & reporting ────────────────────────────────────────────────────

    @property
    def total_proxies(self) -> int:
        return len(self._proxies)

    @property
    def healthy_count(self) -> int:
        return len(self._healthy())

    @property
    def burned_count(self) -> int:
        return self.total_proxies - self.healthy_count

    def stats(self) -> List[Dict]:
        """Return per-proxy health stats."""
        return [
            {
                "proxy": p,
                "failures": self._failure_count[p],
                "successes": self._success_count[p],
                "healthy": self._failure_count[p] < self.max_failures,
            }
            for p in self._proxies
        ]

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _healthy(self) -> List[str]:
        return [p for p in self._proxies if self._failure_count[p] < self.max_failures]

    def _round_robin(self, healthy: List[str]) -> str:
        while True:
            candidate = next(self._rr_cycle)
            if candidate in healthy:
                return candidate
