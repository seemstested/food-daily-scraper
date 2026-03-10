"""
Browser stealth layer — patches navigator properties and injects
realistic human-like interaction patterns to evade bot detection.

Techniques applied:
  - Removes webdriver fingerprint
  - Spoofs navigator.plugins and navigator.languages
  - Injects window.chrome runtime stub
  - Randomises viewport and device memory
  - Applies gaussian-distributed action delays
"""

from __future__ import annotations

import asyncio
import math
import random
from typing import Tuple

from playwright.async_api import Page

from scraper.utils.logger import get_logger

logger = get_logger(__name__)

# JavaScript injected into every new page context before any scripts run
_STEALTH_JS = """
// 1. Remove webdriver flag
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// 2. Realistic plugin list (mimics Chrome on Windows)
const _plugins = [
  { name: 'Chrome PDF Plugin',    filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
  { name: 'Chrome PDF Viewer',    filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
  { name: 'Native Client',        filename: 'internal-nacl-plugin', description: '' },
];
Object.defineProperty(navigator, 'plugins', {
  get: () => {
    const arr = _plugins.map(p => Object.assign(Object.create(Plugin.prototype), p));
    arr.item = (i) => arr[i];
    arr.namedItem = (n) => arr.find(p => p.name === n);
    return Object.assign(arr, { length: _plugins.length });
  }
});

// 3. Language spoofing
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en', 'id'] });

// 4. Chrome runtime stub
if (!window.chrome) {
  window.chrome = { runtime: {}, loadTimes: () => ({}), csi: () => ({}) };
}

// 5. Notification permission
if (window.Notification) {
  Object.defineProperty(Notification, 'permission', { get: () => 'default' });
}

// 6. Device memory (random realistic value)
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

// 7. Hardware concurrency
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });

// 8. Permissions API patch
const _origQuery = window.navigator.permissions?.query.bind(window.navigator.permissions);
if (_origQuery) {
  window.navigator.permissions.query = (params) => (
    params.name === 'notifications'
      ? Promise.resolve({ state: Notification.permission })
      : _origQuery(params)
  );
}
"""


async def apply_stealth(page: Page) -> None:
    """
    Inject all stealth patches into a Playwright page.

    Call this immediately after page creation, before any navigation.

    Args:
        page: The Playwright Page instance to patch.
    """
    await page.add_init_script(_STEALTH_JS)
    logger.debug("Stealth patches applied to page")


async def human_delay(min_ms: int = 800, max_ms: int = 2_500) -> None:
    """
    Wait for a human-like interval, sampled from a truncated normal distribution
    so timings cluster around the midpoint rather than being purely uniform.

    Args:
        min_ms: Minimum delay in milliseconds.
        max_ms: Maximum delay in milliseconds.
    """
    mid = (min_ms + max_ms) / 2
    std = (max_ms - min_ms) / 4
    raw = random.gauss(mid, std)
    clamped = max(min_ms, min(max_ms, raw))
    await asyncio.sleep(clamped / 1_000)


async def human_scroll(page: Page, distance: int = 800, steps: int = 8) -> None:
    """
    Simulate natural page scrolling with variable speed.

    Args:
        page:     Playwright page.
        distance: Total pixels to scroll.
        steps:    Number of intermediate scroll steps.
    """
    per_step = distance // steps
    for i in range(steps):
        # Ease-in-out curve
        progress = i / steps
        ease = 0.5 - math.cos(math.pi * progress) / 2
        delta = int(per_step * (0.5 + ease))
        await page.mouse.wheel(0, delta)
        await asyncio.sleep(random.uniform(0.05, 0.15))


async def human_move_and_click(page: Page, selector: str) -> None:
    """
    Move the mouse naturally to an element before clicking it.

    Args:
        page:     Playwright page.
        selector: CSS selector of the target element.
    """
    element = page.locator(selector).first
    box = await element.bounding_box()
    if box is None:
        await element.click()
        return

    # Landing point with slight randomness inside the element
    x = box["x"] + box["width"] * random.uniform(0.2, 0.8)
    y = box["y"] + box["height"] * random.uniform(0.2, 0.8)

    await page.mouse.move(x, y, steps=random.randint(10, 25))
    await human_delay(100, 300)
    await page.mouse.click(x, y)


def random_viewport() -> Tuple[int, int]:
    """Return a randomised but realistic desktop viewport."""
    options = [
        (1920, 1080),
        (1920, 1200),
        (2560, 1440),
        (1440, 900),
        (1366, 768),
    ]
    return random.choice(options)
