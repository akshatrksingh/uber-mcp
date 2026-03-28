"""Playwright browser session — persistent Chrome profile for uber.com."""
import asyncio
import logging
import os
import sys

from playwright.async_api import BrowserContext, Page, async_playwright

logger = logging.getLogger(__name__)

_PROFILE_DIR = os.path.expanduser('~/.uber-mcp/chrome-profile')
_CHROME_BIN = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
_UBER_URL = 'https://www.uber.com/us/en/rider-home/'

# Selector present on the logged-in rider-home booking form.
_LOGGED_IN_SEL = '[data-uweb-guide-key="RV_PUDO_PICKUP_INPUT"], input[aria-label="destination location input"]'


class BrowserSession:
    """Manages a persistent Chrome profile context for uber.com."""

    def __init__(self) -> None:
        self._pw = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self.is_logged_in: bool = False

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError('BrowserSession.start() not called')
        return self._page

    async def start(self) -> None:
        """Launch Chrome with a persistent profile. No-op if already running."""
        if self._page is not None:
            return
        self._pw = await async_playwright().start()
        self._context = await self._pw.chromium.launch_persistent_context(
            _PROFILE_DIR,
            executable_path=_CHROME_BIN,
            headless=False,
            no_viewport=True,
            args=['--disable-blink-features=AutomationControlled'],
        )
        # Reuse the first page opened by Chrome (avoids a blank extra tab).
        pages = self._context.pages
        self._page = pages[0] if pages else await self._context.new_page()
        logger.info('Browser session started (persistent profile: %s)', _PROFILE_DIR)

    async def stop(self) -> None:
        """Close the browser gracefully."""
        if self._context:
            await self._context.close()
        if self._pw:
            await self._pw.stop()
        self._page = self._context = self._pw = None
        logger.info('Browser session closed')

    async def ensure_logged_in(self) -> bool:
        """Navigate to uber.com and verify login by looking for ride-booking elements.

        If the page shows a signup/login state instead of the booking UI, prompts
        the user to log in manually and polls for up to 120 seconds.

        Returns:
            True if logged-in state is detected, False if 120-second timeout elapsed.
        """
        page = self.page
        try:
            await page.goto(_UBER_URL, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(2)
        except Exception as exc:
            logger.error('Navigation to uber.com failed: %s', exc)
            return False

        if await self._is_logged_in():
            logger.info('Already logged in — ride booking UI detected')
            self.is_logged_in = True
            return True

        logger.info('Not logged in — waiting for manual login')
        print(
            '\n[uber-mcp] Please log in to Uber in the browser window.'
            ' You have 120 seconds.\n',
            file=sys.stderr,
            flush=True,
        )

        for _ in range(60):
            await asyncio.sleep(2)
            if await self._is_logged_in():
                logger.info('Login detected — ride booking UI appeared')
                break
        else:
            logger.warning('Login timeout — ride booking UI did not appear within 120 seconds')
            self.is_logged_in = False
            return False

        self.is_logged_in = True
        logger.info('Logged in to Uber')
        return True

    async def _is_logged_in(self) -> bool:
        """Return True if the ride-booking destination input is visible on the page."""
        try:
            el = self._page.locator(_LOGGED_IN_SEL).first
            return await el.is_visible(timeout=3000)
        except Exception:
            return False
