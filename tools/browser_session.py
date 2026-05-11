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
from typing import Iterator

from playwright.sync_api import BrowserContext, Page, sync_playwright

from tools._common import storage_state_path


X_HOME = "https://x.com/home"


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
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            storage_state=str(state_path),
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()
        try:
            yield context, page
        finally:
            # Persist any refreshed cookies / local storage
            context.storage_state(path=str(state_path))
            context.close()
            browser.close()


def interactive_login() -> None:
    """Open a headful browser, let the user log in manually, save the session."""
    state_path = storage_state_path()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()
        page.goto("https://x.com/login")
        print("\n>>> Log in to X in the browser window that just opened.")
        print(">>> Complete 2FA if prompted.")
        print(">>> When you can see your home timeline, come back here and press Enter.\n")
        input("Press Enter when you're logged in… ")
        context.storage_state(path=str(state_path))
        print(f"Saved session to {state_path}")
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
