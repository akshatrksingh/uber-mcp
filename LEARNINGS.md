# Learnings

## Uber API is gated behind business partnerships

I started assuming the Riders API would be available — built the initial mock provider around its expected responses based on docs available online. Later realized the API is gated: you need to contact Uber and get whitelisted. I tried creating apps under multiple API suites (Others, Uber Third Party Support, Rider3PLTesting) — none granted scope access.

Learning: verify API access granularly before building around it. This was a small-scale project with a clear alternative, so pivoting wasn't painful. But in a production setting, discovering your core dependency is locked behind a business relationship after building around it could be scary.

## Browser automation was the practical pivot

Pivoted to Playwright-based browser automation — same approach used by some examples I found online - Uber Eats MCP server and the Lyft MCP server in the wild. Getting it to work was its own journey:

- Bundled Chromium gets bot-detected immediately by Uber
- `m.uber.com` has aggressive anti-bot reload loops
- Fresh Chrome profiles trigger CAPTCHA every time
- Fix: `launch_persistent_context` with the real Chrome binary + `--disable-blink-features=AutomationControlled` + a dedicated profile directory at `~/.uber-mcp/chrome-profile`
- One manual login, then hands-free forever — Chrome's own session management handles persistence

Scraping was fragile too. CSS class selectors broke across Uber's deploys. Switched to grabbing each card's full `inner_text()` and parsing with regex — way more stable. The pickup input requires clicking a container div (`data-uweb-guide-key`) because child elements intercept pointer events. Destination input needs `force=True`. These are the kinds of things you only learn by debugging live.

## MCP's provider abstraction held up perfectly

The agent code and all seven tool definitions never changed across three provider implementations: mock → Uber API client → browser automation. The only thing that swapped was the provider registered in `src/provider.py`. That's MCP working exactly as designed — tools define the interface, providers are swappable underneath.

## This approach has a shelf life

Browser automation against uber.com works today, but it's subject to UI changes. If Uber updates their frontend — different selectors, different flow — the scraping breaks. An actual API integration would be more stable and maintainable. The architecture is ready for that swap if API access ever becomes available.

## Overall

Fun project. Went from "this should be straightforward with the Uber API" to "oh, the API is locked" to "let me automate a browser" to "the browser detects me as a bot" to "finally, real ride prices showing up in my terminal." The debugging journey was the real learning.
