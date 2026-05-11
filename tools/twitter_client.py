"""
X (Twitter) actions built on top of a Playwright session.

Two capabilities:

1. `fetch_mutuals(handle)` — scrapes your followers and following lists by
   scrolling the rendered virtual lists, then intersects them. Slow but
   robust to logged-in DOM changes because it relies on stable data-testid
   attributes.

2. `send_dm(handle, message)` — navigates to the recipient's profile, clicks
   the message button, types into the composer, sends.

DM sending is brittle by nature. Each call returns a typed result so the
caller can record outcomes per-row in the state sheet rather than failing the
whole batch.
"""
from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from typing import Literal

from playwright.sync_api import Page, TimeoutError as PWTimeout


# data-testid values are the most stable hooks inside X's React app. The
# class names are obfuscated and change between deploys, but testids have
# survived years of redesigns.
USER_CELL = '[data-testid="UserCell"]'
DM_INBOX_LINK = '[data-testid="AppTabBar_DirectMessage_Link"]'
DM_TEXTAREA = '[data-testid="dmComposerTextInput"]'
DM_SEND_BUTTON = '[data-testid="dmComposerSendButton"]'
PROFILE_DM_BUTTON = '[data-testid="sendDMFromProfile"]'


SendStatus = Literal["sent", "no_dm_button", "blocked", "navigation_failed", "send_failed"]


@dataclass
class SendResult:
    status: SendStatus
    detail: str = ""


def _humanlike_pause(min_ms: int = 600, max_ms: int = 1800) -> None:
    time.sleep(random.uniform(min_ms / 1000, max_ms / 1000))


def _collect_user_cells(page: Page) -> set[str]:
    """Read every currently-rendered UserCell on the page and return handles."""
    handles: set[str] = set()
    cells = page.query_selector_all(USER_CELL)
    for cell in cells:
        # Each UserCell contains an anchor whose href is /<handle>
        link = cell.query_selector('a[role="link"][href^="/"]')
        if not link:
            continue
        href = link.get_attribute("href") or ""
        m = re.match(r"^/([A-Za-z0-9_]+)$", href)
        if m:
            handles.add(m.group(1).lower())
    return handles


def _scroll_collect(page: Page, max_idle_rounds: int = 4, max_seconds: int = 180) -> set[str]:
    """Scroll until no new UserCells appear for `max_idle_rounds` consecutive rounds."""
    seen: set[str] = set()
    idle = 0
    started = time.time()
    while True:
        new = _collect_user_cells(page) - seen
        if new:
            seen.update(new)
            idle = 0
        else:
            idle += 1
        if idle >= max_idle_rounds:
            break
        if time.time() - started > max_seconds:
            break
        page.mouse.wheel(0, 2000)
        _humanlike_pause(700, 1400)
    return seen


def fetch_followers(page: Page, handle: str) -> set[str]:
    page.goto(f"https://x.com/{handle}/verified_followers", wait_until="domcontentloaded")
    # Verified Followers is the only page X still renders without truncation
    # for your own profile. For followers in general, fall back to /followers.
    if "Page not found" in page.content() or "/verified_followers" not in page.url:
        page.goto(f"https://x.com/{handle}/followers", wait_until="domcontentloaded")
    page.wait_for_selector(USER_CELL, timeout=20000)
    return _scroll_collect(page)


def fetch_following(page: Page, handle: str) -> set[str]:
    page.goto(f"https://x.com/{handle}/following", wait_until="domcontentloaded")
    page.wait_for_selector(USER_CELL, timeout=20000)
    return _scroll_collect(page)


def fetch_mutuals(page: Page, handle: str) -> list[str]:
    """Return the lowercase handles of accounts you follow AND that follow you."""
    handle = handle.lstrip("@").lower()
    following = fetch_following(page, handle)
    followers = fetch_followers(page, handle)
    return sorted(following & followers)


def fetch_display_name(page: Page, handle: str) -> str | None:
    """Best-effort display-name lookup for personalising messages."""
    try:
        page.goto(f"https://x.com/{handle}", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_selector('[data-testid="UserName"]', timeout=8000)
        el = page.query_selector('[data-testid="UserName"] span span')
        if el:
            return (el.inner_text() or "").strip() or None
    except PWTimeout:
        return None
    return None


def send_dm(page: Page, handle: str, message: str) -> SendResult:
    """Send a DM to `handle`. Returns a structured result; never raises on
    expected failure modes (no DM button, blocked, etc.).
    """
    handle = handle.lstrip("@")
    try:
        page.goto(f"https://x.com/{handle}", wait_until="domcontentloaded", timeout=20000)
    except PWTimeout:
        return SendResult("navigation_failed", "profile did not load in time")

    # Bail if X redirected us anywhere unexpected (suspended, restricted, etc.)
    if f"/{handle.lower()}" not in page.url.lower():
        return SendResult("navigation_failed", f"unexpected URL: {page.url}")

    _humanlike_pause()

    dm_button = page.query_selector(PROFILE_DM_BUTTON)
    if not dm_button:
        # No DM button means: not a mutual, DMs closed, blocked, or suspended.
        return SendResult("no_dm_button", "no message button on profile")

    dm_button.click()
    try:
        page.wait_for_selector(DM_TEXTAREA, timeout=15000)
    except PWTimeout:
        return SendResult("send_failed", "composer never appeared")

    _humanlike_pause()
    composer = page.query_selector(DM_TEXTAREA)
    if not composer:
        return SendResult("send_failed", "composer query returned nothing")

    composer.click()
    # Typing slowly looks more human than `fill`; X's spam heuristics weigh this.
    page.keyboard.type(message, delay=random.randint(35, 90))
    _humanlike_pause(800, 1600)

    send_btn = page.query_selector(DM_SEND_BUTTON)
    if not send_btn:
        return SendResult("send_failed", "no send button after typing")

    # Disabled send button = X considers the message empty / invalid.
    is_disabled = send_btn.get_attribute("aria-disabled") == "true"
    if is_disabled:
        return SendResult("send_failed", "send button disabled")

    send_btn.click()
    _humanlike_pause(1500, 2500)

    # Empirically: a successful send clears the composer. Use that as the
    # confirmation signal rather than searching for the new message bubble,
    # which is virtualized and hard to assert against reliably.
    remaining = page.query_selector(DM_TEXTAREA)
    if remaining:
        remaining_text = (remaining.inner_text() or "").strip()
        if remaining_text and remaining_text == message.strip():
            return SendResult("send_failed", "composer still has the message after send")

    return SendResult("sent", "")
