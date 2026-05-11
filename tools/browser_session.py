"""
Playwright session manager for X (Twitter).

First run:  python tools/browser_session.py login
            ↳ opens a real Chromium window. Log in to X by hand, including 2FA.
              When you see your timeline, press Enter in the terminal. The
              session cookies are saved to storage_state.json and reused on
              every subsequent run.

Health check: python tools/browser_session.py check
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# When run as `python tools/browser_session.py …`, Python puts `tools/` on
# sys.path but not the project root, so `from tools._common …` fails. This
# block makes the file runnable both as a script and as a module.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from playwright.sync_api import BrowserContext, Page, sync_playwright  # noqa: E402

from tools._common import storage_state_path  # noqa: E402


X_HOME = "https://x.com/home"


def _launch_browser(p, *, headless: bool):
    """Launch the real installed Chrome, not Playwright's bundled Chromium.

    X's login JS checks `navigator.webdriver` and bounces automated browsers
    in a silent loop. The flags below remove the obvious automation tells
    that Chromium sets by default. We also use channel="chrome" so we run
    against the actual Chrome that's installed on this machine, with its
    full normal fingerprint, rather than the slightly off Chromium binary
    Playwright ships.
    """
    return p.chromium.launch(
        channel="chrome",
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-default-browser-check",
            "--no-first-run",
        ],
        ignore_default_args=["--enable-automation"],
    )


def _new_context(browser, *, storage_state: str | None = None):
    context = browser.new_context(
        storage_state=storage_state,
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 900},
        locale="en-US",
    )
    # One more layer: even after stripping --enable-automation, JS-level
    # detection of navigator.webdriver still fires. Override it on every
    # page load.
    context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    )
    return context


@contextmanager
def x_session(*, headless: bool = True) -> Iterator[tuple[BrowserContext, Page]]:
    """Yield a Playwright context + page already authenticated to X.

    Loads cookies from storage_state.json if it exists; otherwise raises so
    the caller can prompt for a one-time login.
    """
    state_path = storage_state_path()
    if not state_path.exists():
        raise RuntimeError(
            f"No saved X session at {state_path}. "
            "Run: python tools/browser_session.py login"
        )

    with sync_playwright() as p:
        browser = _launch_browser(p, headless=headless)
        context = _new_context(browser, storage_state=str(state_path))
        page = context.new_page()
        try:
            yield context, page
        finally:
            # Persist any refreshed cookies / local storage
            context.storage_state(path=str(state_path))
            context.close()
            browser.close()


def interactive_login(*, wait_seconds: int = 600) -> None:
    """Open a headful browser, wait for the user to reach the home timeline,
    save the session automatically, close the window.

    Polls the page URL every 2 seconds for up to `wait_seconds`. The flow ends
    when the URL contains `/home` (the post-login destination on x.com).
    No terminal input is required — this works in any environment that can
    launch a window, including when something else (Claude, a parent script,
    a button in the web UI) kicks it off.
    """
    import time

    state_path = storage_state_path()
    with sync_playwright() as p:
        browser = _launch_browser(p, headless=False)
        context = _new_context(browser)
        page = context.new_page()
        page.goto("https://x.com/login")
        print(">>> Log in to X in the browser window that just opened.")
        print(">>> Complete 2FA if prompted. The window closes itself once you reach the home timeline.")
        deadline = time.time() + wait_seconds
        # Detection rule: any x.com URL that is NOT a login/flow page. This
        # covers /home, /i/timeline, onboarding interstitials, and the
        # "phone number / interests" prompts X sometimes shows post-login.
        # We also require an `auth_token` cookie as a hard confirmation —
        # the only authenticated state X actually persists.
        while time.time() < deadline:
            try:
                url = page.url
                cookies = {c["name"] for c in context.cookies()}
            except Exception:
                url = ""
                cookies = set()
            on_x = "x.com" in url or "twitter.com" in url
            in_login_flow = "/login" in url or "/i/flow/login" in url or "/i/flow/signup" in url
            logged_in = "auth_token" in cookies
            if on_x and not in_login_flow and logged_in:
                context.storage_state(path=str(state_path))
                print(f"Login detected at {url}. Saved session to {state_path}")
                browser.close()
                return
            time.sleep(2)
        print(f"Timed out after {wait_seconds}s without seeing /home. No session saved.")
        browser.close()


def health_check() -> int:
    """Open the saved session and confirm we land on the timeline (not /login)."""
    try:
        with x_session(headless=True) as (_ctx, page):
            page.goto(X_HOME, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2000)
            url = page.url
            if "/login" in url or "/flow/login" in url:
                print(f"FAIL: redirected to login ({url}). Re-run `login`.")
                return 1
            print(f"OK: logged in. Current URL: {url}")
            return 0
    except Exception as e:
        print(f"FAIL: {e}")
        return 1


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "login":
        interactive_login()
    elif cmd == "check":
        sys.exit(health_check())
    else:
        print(__doc__)
        sys.exit(2)
