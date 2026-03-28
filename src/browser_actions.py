"""Low-level Playwright interactions for uber.com/us/en/rider-home/.

All functions take a Playwright Page as the first argument and are stateless.
Update the SEL constants below if Uber changes their frontend.
"""
import asyncio
import logging
import re

from playwright.async_api import Page

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SEL constants — update these when Uber's frontend changes.
# ---------------------------------------------------------------------------

# Cookie / consent banner
_COOKIE_BTN = 'button:has-text("Got it"), button:has-text("Accept"), button:has-text("Accept cookies")'

# Pickup: click the container div (inner elements intercept pointer events)
_PICKUP_CONTAINER = '[data-uweb-guide-key="RV_PUDO_PICKUP_INPUT"]'

# Destination: force-click required because overlapping elements block normal click
_DEST_INPUT = 'input[aria-label="destination location input"]'

# Autocomplete suggestion list
_SUGGESTION = '[role="option"]:visible'

# "See prices" text link/button — clicking navigates to m.uber.com/go/product-selection
_SEE_PRICES_BTN = 'text=See prices'

# URL fragment that confirms we reached the product-selection page
_PRODUCT_URL = 'product-selection'

# Product cards on m.uber.com/go/product-selection
_PRODUCT_CARDS = '[data-testid="product-tile"]:visible, [role="radio"]:visible, [data-testid*="product"]:visible'

# Sub-element selectors used only for click_product fare scrape after card selection.
_PRICE_EL = '[class*="price" i], [class*="fare" i], [class*="estimate" i], [data-testid*="price"]'

# "Request <product>" button at the bottom of product-selection
_REQUEST_BTN = 'button:has-text("Request"), button:has-text("Confirm"), button:has-text("Book")'

# Active-ride screen elements
_DRIVER_NAME = '[data-testid="driver-name"], [class*="DriverName" i], [class*="driver-name" i]'
_ETA_ACTIVE  = '[class*="eta" i]:visible, [class*="arrive" i]:visible'

# Cancel buttons
_CANCEL_BTN     = 'button:has-text("Cancel")'
_CANCEL_CONFIRM = 'button:has-text("Cancel ride"), button:has-text("Yes, cancel"), button:has-text("Confirm cancel")'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _screenshot(page: Page, label: str) -> None:
    """Save a debug screenshot to /tmp/uber_mcp_{label}.png."""
    path = f'/tmp/uber_mcp_{label}.png'
    try:
        await page.screenshot(path=path, full_page=False)
        logger.info('Screenshot saved: %s', path)
    except Exception as exc:
        logger.warning('Screenshot failed (%s): %s', label, exc)


async def safe_text(page: Page, selector: str, timeout: int = 4000) -> str:
    """Return inner text of the first matching element, or '' on any failure."""
    try:
        return await page.locator(selector).first.inner_text(timeout=timeout)
    except Exception:
        return ''


async def dismiss_cookie_banner(page: Page) -> None:
    """Click the cookie consent button if it is visible."""
    try:
        btn = page.locator(_COOKIE_BTN).first
        if await btn.is_visible(timeout=3000):
            await btn.click()
            await asyncio.sleep(0.5)
            logger.info('Cookie banner dismissed')
    except Exception:
        pass  # No banner — that's fine


async def fill_address(page: Page, index: int, address: str) -> bool:
    """Type an address into the pickup (0) or destination (1) input and pick the first autocomplete result.

    Pickup uses the data-uweb-guide-key container click (inner elements intercept
    pointer events on direct input click). Destination uses force=True on the
    aria-label input to bypass overlapping elements.

    Args:
        page: Playwright Page.
        index: 0 for pickup, 1 for destination.
        address: Text to type.

    Returns:
        True on success, False on failure.
    """
    await dismiss_cookie_banner(page)
    label = 'pickup' if index == 0 else 'destination'
    try:
        if index == 0:
            await page.click(_PICKUP_CONTAINER)
        else:
            await page.locator(_DEST_INPUT).first.click(force=True)

        await page.keyboard.type(address, delay=80)
        await _screenshot(page, f'after_type_{label}')

        await asyncio.sleep(3)  # wait for autocomplete network request
        suggestion = page.locator(_SUGGESTION).first
        await suggestion.wait_for(state='visible', timeout=5000)
        await _screenshot(page, f'after_suggestions_{label}')
        await suggestion.click()
        await asyncio.sleep(0.8)
        await _screenshot(page, f'after_select_{label}')
        return True
    except Exception as exc:
        logger.error('fill_address[%d] %r: %s', index, address, exc)
        await _screenshot(page, f'error_{label}')
        return False


async def click_see_prices(page: Page) -> bool:
    """Click 'See prices' and wait for navigation to the product-selection page.

    After clicking, Uber navigates from uber.com to m.uber.com/go/product-selection.
    We wait for the URL to contain 'product-selection' before returning.

    Args:
        page: Playwright Page.

    Returns:
        True if product-selection page is reached, False on timeout or error.
    """
    try:
        btn = page.locator(_SEE_PRICES_BTN).first
        await btn.wait_for(state='visible', timeout=8000)
        await btn.click()
        logger.info('"See prices" clicked — waiting for product-selection page')
        await page.wait_for_url(f'**/{_PRODUCT_URL}**', timeout=15000)
        await _screenshot(page, 'product_selection_page')
        return True
    except Exception as exc:
        logger.error('click_see_prices: %s', exc)
        await _screenshot(page, 'error_see_prices')
        return False


async def scrape_product_cards(page: Page) -> list[dict]:
    """Wait for and scrape all visible product cards from the product-selection screen.

    Grabs each card's full inner_text() and parses it with regex — more robust
    than nested CSS selectors whose class names change with Uber deploys.

    Expected inner text format (lines vary):
        "UberX\\n4\\n2 mins away · 12:11 AM\\nFaster\\n$27.15\\n$31.45"

    Args:
        page: Playwright Page (should be on m.uber.com/go/product-selection).

    Returns:
        List of option dicts; empty list if none found or scraping fails.
    """
    try:
        cards = page.locator('[data-testid*="product"]:visible, [role="radio"]:visible')
        await cards.first.wait_for(state='visible', timeout=20000)
        await _screenshot(page, 'product_cards')
        options = []
        for i in range(await cards.count()):
            try:
                text = await cards.nth(i).inner_text(timeout=5000)
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                if not lines:
                    continue

                # First non-empty line is the product name, possibly suffixed by the
                # capacity digit with no separator (e.g. "UberX4"). Strip trailing digits
                # to isolate the clean name.
                raw_name = lines[0]
                name = re.sub(r'\d+$', '', raw_name).strip() or raw_name
                product_id = re.sub(r'\s+', '', name.lower())

                # All dollar amounts — first is estimate_low, second (if present) is estimate_high.
                prices = re.findall(r'\$(\d+(?:\.\d+)?)', text)
                estimate_low  = float(prices[0]) if prices else 0.0
                estimate_high = float(prices[1]) if len(prices) > 1 else estimate_low

                # Skip ghost/sub-element cards: no price, or name starts with a digit.
                if (estimate_low == 0 and estimate_high == 0) or raw_name[0].isdigit():
                    continue

                # "N mins away" → ETA.
                eta_match = re.search(r'(\d+)\s*min', text, re.IGNORECASE)
                eta_minutes = int(eta_match.group(1)) if eta_match else 0

                # Standalone integer on its own line → seat capacity (e.g. "4").
                capacity = 0
                for line in lines[1:]:
                    if re.fullmatch(r'\d+', line):
                        capacity = int(line)
                        break

                options.append({
                    'product_id':    product_id,
                    'name':          name,
                    'estimate_low':  estimate_low,
                    'estimate_high': estimate_high,
                    'currency':      'USD',
                    'eta_minutes':   eta_minutes,
                    'capacity':      capacity,
                })
                logger.info('Card %d: %s $%.2f–%.2f %d min cap=%d',
                            i, name, estimate_low, estimate_high, eta_minutes, capacity)
            except Exception as exc:
                logger.warning('Card %d parse failed: %s', i, exc)
        return options
    except Exception as exc:
        logger.error('scrape_product_cards: %s', exc)
        await _screenshot(page, 'error_product_cards')
        return []


async def click_product(page: Page, product_id: str) -> tuple[str, str]:
    """Click the product card matching product_id and return (name, fare_text).

    Args:
        page: Playwright Page.
        product_id: Slug like 'uberx' or 'share'.

    Returns:
        (product_name, fare_display_text) or ('', '') if not found.
    """
    cards = page.locator('[data-testid*="product"]:visible, [role="radio"]:visible')
    for i in range(await cards.count()):
        card = cards.nth(i)
        try:
            text = await card.inner_text(timeout=5000)
            raw_name = text.splitlines()[0].strip() if text.strip() else ''
            name = re.sub(r'\d+$', '', raw_name).strip() or raw_name
            if re.sub(r'\s+', '', name.lower()) == product_id:
                await card.click()
                await asyncio.sleep(1)
                await _screenshot(page, f'after_select_product_{product_id}')
                fare = await safe_text(page, f'{_PRICE_EL}:visible')
                return name, fare
        except Exception:
            continue
    await _screenshot(page, f'error_product_not_found_{product_id}')
    return '', ''


async def click_request(page: Page) -> tuple[str, str]:
    """Click the 'Request <product>' button and scrape driver name and ETA text.

    Args:
        page: Playwright Page.

    Returns:
        (driver_name, eta_raw_text).
    """
    btn = page.locator(_REQUEST_BTN).first
    await btn.wait_for(state='visible', timeout=10000)
    await btn.click()
    await asyncio.sleep(3)
    await _screenshot(page, 'after_request')
    driver = await safe_text(page, _DRIVER_NAME)
    eta    = await safe_text(page, _ETA_ACTIVE)
    return driver, eta


async def click_cancel(page: Page) -> bool:
    """Click Cancel button and confirm in any resulting dialog.

    Args:
        page: Playwright Page.

    Returns:
        True if cancel button was found and clicked, False otherwise.
    """
    try:
        btn = page.locator(_CANCEL_BTN).first
        await btn.wait_for(state='visible', timeout=10000)
        await btn.click()
        await asyncio.sleep(1)
        confirm = page.locator(_CANCEL_CONFIRM).first
        if await confirm.is_visible(timeout=3000):
            await confirm.click()
        await _screenshot(page, 'after_cancel')
        return True
    except Exception as exc:
        logger.error('click_cancel: %s', exc)
        await _screenshot(page, 'error_cancel')
        return False
