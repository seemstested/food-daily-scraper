"""
Unit tests for the ProxyManager.
"""

from __future__ import annotations

import pytest

from scraper.exceptions import NoProxyAvailableError
from scraper.utils.proxy_manager import ProxyManager


PROXIES = [
    "http://user:pass@p1.example.com:8080",
    "http://user:pass@p2.example.com:8080",
    "http://user:pass@p3.example.com:8080",
]


class TestProxyManagerInit:
    def test_initialises_with_proxy_list(self):
        pm = ProxyManager(PROXIES)
        assert pm.total_proxies == 3
        assert pm.healthy_count == 3
        assert pm.burned_count == 0

    def test_empty_proxy_list_returns_none(self):
        pm = ProxyManager([])
        assert pm.get_proxy() is None

    def test_invalid_strategy_still_defaults(self):
        pm = ProxyManager(PROXIES, strategy="nonexistent")
        # Falls through to least_failed
        proxy = pm.get_proxy()
        assert proxy in PROXIES


class TestProxySelection:
    def test_least_failed_picks_healthy_proxy(self, proxy_manager):
        proxy = proxy_manager.get_proxy()
        pm_proxies = [p["proxy"] for p in proxy_manager.stats()]
        assert proxy in pm_proxies

    def test_round_robin_cycles(self):
        pm = ProxyManager(PROXIES, strategy="round_robin")
        seen = [pm.get_proxy() for _ in range(len(PROXIES))]
        # Should have visited all proxies
        assert set(seen) == set(PROXIES)

    def test_random_strategy_returns_valid_proxy(self):
        pm = ProxyManager(PROXIES, strategy="random")
        for _ in range(20):
            p = pm.get_proxy()
            assert p in PROXIES


class TestProxyHealthTracking:
    def test_mark_failure_increments_count(self, proxy_manager):
        proxy = PROXIES[0]
        proxy_manager.mark_failure(proxy)
        assert proxy_manager._failure_count[proxy] == 1

    def test_mark_success_decrements_failure(self, proxy_manager):
        proxy = PROXIES[0]
        proxy_manager.mark_failure(proxy)
        proxy_manager.mark_failure(proxy)
        proxy_manager.mark_success(proxy)
        assert proxy_manager._failure_count[proxy] == 1

    def test_failure_count_never_below_zero(self, proxy_manager):
        proxy = PROXIES[0]
        proxy_manager.mark_success(proxy)
        proxy_manager.mark_success(proxy)
        assert proxy_manager._failure_count[proxy] == 0

    def test_burned_proxy_excluded_from_selection(self):
        pm = ProxyManager([PROXIES[0], PROXIES[1]], max_failures=2)
        pm.mark_failure(PROXIES[0])
        pm.mark_failure(PROXIES[0])
        # PROXIES[0] is burned; only PROXIES[1] available
        for _ in range(10):
            assert pm.get_proxy() == PROXIES[1]

    def test_all_proxies_burned_raises(self):
        pm = ProxyManager([PROXIES[0]], max_failures=1)
        pm.mark_failure(PROXIES[0])
        with pytest.raises(NoProxyAvailableError):
            pm.get_proxy()

    def test_reset_clears_failure_counts(self, proxy_manager):
        proxy_manager.mark_failure(PROXIES[0])
        proxy_manager.mark_failure(PROXIES[0])
        proxy_manager.reset(PROXIES[0])
        assert proxy_manager._failure_count[PROXIES[0]] == 0

    def test_reset_all_clears_everything(self, proxy_manager):
        for p in PROXIES:
            proxy_manager.mark_failure(p)
        proxy_manager.reset()
        for p in PROXIES:
            assert proxy_manager._failure_count[p] == 0

    def test_stats_returns_per_proxy_info(self, proxy_manager):
        first_proxy = proxy_manager.get_proxy()
        proxy_manager.mark_failure(first_proxy)
        stats = proxy_manager.stats()
        assert len(stats) == 3
        p0_stat = next(s for s in stats if s["proxy"] == first_proxy)
        assert p0_stat["failures"] == 1
        assert p0_stat["healthy"] is True  # max_failures=2, only 1 failure


class TestProxyManagerCounting:
    def test_healthy_count_decreases_on_burn(self):
        pm = ProxyManager(PROXIES, max_failures=1)
        assert pm.healthy_count == 3
        pm.mark_failure(PROXIES[0])
        assert pm.healthy_count == 2
        assert pm.burned_count == 1
