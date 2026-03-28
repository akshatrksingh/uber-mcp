"""First-time Uber browser auth setup.

Launches Chrome with the persistent profile, navigates to uber.com, and waits
for the user to log in. Once the ride-booking form is detected, saves the session
and exits. Subsequent agent runs are fully hands-free.

Usage:
    uv run python setup_browser.py
"""
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

_PROFILE_DIR = Path.home() / '.uber-mcp' / 'chrome-profile'
_CHROME_BIN  = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
_UBER_URL    = 'https://www.uber.com/us/en/rider-home/'

# Selector present on the logged-in booking form (same as browser_session._LOGGED_IN_SEL)
_LOGGED_IN_SEL = '[data-uweb-guide-key="RV_PUDO_PICKUP_INPUT"], input[aria-label="destination location input"]'


async def _wait_for_login(timeout_seconds: int = 120) -> bool:
    """Open Chrome, navigate to uber.com, poll for login, return True on success."""
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            str(_PROFILE_DIR),
            executable_path=_CHROME_BIN,
            headless=False,
            no_viewport=True,
            args=['--disable-blink-features=AutomationControlled'],
        )
        pages = ctx.pages
        page = pages[0] if pages else await ctx.new_page()

        await page.goto(_UBER_URL, wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(2)

        # Check if already logged in.
        try:
            if await page.locator(_LOGGED_IN_SEL).first.is_visible(timeout=3000):
                print('Already logged in — session is valid.')
                await ctx.close()
                return True
        except Exception:
            pass

        print(f'Please log in to Uber in the browser window. You have {timeout_seconds} seconds.')

        for _ in range(timeout_seconds // 2):
            await asyncio.sleep(2)
            try:
                if await page.locator(_LOGGED_IN_SEL).first.is_visible(timeout=1000):
                    print('Login successful! Session saved.')
                    await ctx.close()
                    return True
            except Exception:
                continue

        print('Timed out waiting for login.', file=sys.stderr)
        await ctx.close()
        return False


def main() -> None:
    _PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    print('Uber MCP — first-time browser setup')
    print(f'Profile directory: {_PROFILE_DIR}')
    print()

    success = asyncio.run(_wait_for_login())
    if success:
        print('You can now run the agent: uv run python -m agent.cli_agent')
        sys.exit(0)
    else:
        print('Setup failed. Run setup_browser.py again to retry.', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
