"""
Google Sheets state store for Xequence.

Schema (one row per (handle, sequence) pair):

    handle          | x username, no @
    display_name    | scraped display name, used for {first_name}
    sequence        | name of the sequence YAML to follow
    enrolled_at     | ISO8601 UTC datetime
    current_step    | 0-indexed, next step to send
    next_send_at    | ISO8601 UTC datetime — when current_step is due
    last_sent_at    | ISO8601 UTC datetime of the most recent send
    status          | pending | in_progress | completed | error | stopped
    notes           | freeform; used to surface send errors

The first time you call ensure_sheet(), the header row is created if missing.

Caching: the gspread Client and Worksheet objects are cached at module level
after their first use. Without this, a single tick over 10 contacts can fire
~30 read requests at the Sheets API — well past the default 60/min quota.
With caching, each update is one write request and that's it.
"""
from __future__ import annotations

import random
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, TypeVar

import gspread
from google.oauth2.service_account import Credentials

from tools._common import env


HEADERS = [
    "handle",
    "display_name",
    "sequence",
    "enrolled_at",
    "current_step",
    "next_send_at",
    "last_sent_at",
    "status",
    "notes",
]


def _extract_sheet_id(value: str) -> str:
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", value)
    return m.group(1) if m else value


# Process-level singletons. The gspread Client is cheap to reuse; the
# Worksheet object encapsulates the spreadsheet + tab and survives across
# operations. Resetting them only matters if creds or the sheet ID change at
# runtime, which we don't support.
_lock = threading.Lock()
_client_cache: gspread.Client | None = None
_worksheet_cache: gspread.Worksheet | None = None
_header_verified = False


def _client() -> gspread.Client:
    global _client_cache
    if _client_cache is not None:
        return _client_cache
    sa_path = Path(env("GOOGLE_SERVICE_ACCOUNT_JSON", required=True))
    if not sa_path.is_absolute():
        sa_path = (Path(__file__).resolve().parent.parent / sa_path).resolve()
    creds = Credentials.from_service_account_file(
        str(sa_path),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
        ],
    )
    _client_cache = gspread.authorize(creds)
    return _client_cache


def _worksheet() -> gspread.Worksheet:
    global _worksheet_cache, _header_verified
    with _lock:
        if _worksheet_cache is not None and _header_verified:
            return _worksheet_cache
        sh_id = _extract_sheet_id(env("XEQUENCE_SHEET_ID", required=True))
        tab = env("XEQUENCE_SHEET_TAB", "contacts")
        sh = _client().open_by_key(sh_id)
        try:
            ws = sh.worksheet(tab)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=tab, rows=1000, cols=len(HEADERS))
        # Header verify happens exactly once per process — every subsequent
        # call goes straight through. This is the call that used to burn
        # one read per contact during a tick.
        first_row = ws.row_values(1)
        if first_row != HEADERS:
            ws.update("A1", [HEADERS])
        _worksheet_cache = ws
        _header_verified = True
        return ws


T = TypeVar("T")


def _retry_on_quota(func: Callable[..., T]) -> Callable[..., T]:
    """Retry an API call on 429 / quota errors with exponential backoff +
    jitter. Up to 4 attempts (5s, 11s, 22s, 45s). After that, re-raise so
    the caller can surface the failure in the UI."""
    def wrapper(*args, **kwargs):
        for attempt in range(4):
            try:
                return func(*args, **kwargs)
            except gspread.exceptions.APIError as e:
                msg = str(e)
                is_quota = "429" in msg or "Quota exceeded" in msg or "RATE_LIMIT" in msg
                if not is_quota or attempt == 3:
                    raise
                delay = (2 ** attempt) * 5 + random.uniform(0, 2)
                time.sleep(delay)
        raise RuntimeError("unreachable")
    return wrapper


@dataclass
class Contact:
    handle: str
    display_name: str = ""
    sequence: str = "default"
    enrolled_at: str = ""
    current_step: int = 0
    next_send_at: str = ""
    last_sent_at: str = ""
    status: str = "pending"
    notes: str = ""
    # Internal — the spreadsheet row number this contact lives at (1-indexed,
    # including the header). Set after read. Used for in-place updates.
    _row: int = field(default=0, repr=False)

    @classmethod
    def from_row(cls, row: list[str], row_index: int) -> "Contact":
        # Pad short rows so positional access is safe
        padded = row + [""] * (len(HEADERS) - len(row))
        return cls(
            handle=padded[0].strip().lower(),
            display_name=padded[1],
            sequence=padded[2] or "default",
            enrolled_at=padded[3],
            current_step=int(padded[4]) if padded[4].strip().isdigit() else 0,
            next_send_at=padded[5],
            last_sent_at=padded[6],
            status=padded[7] or "pending",
            notes=padded[8],
            _row=row_index,
        )

    def to_row(self) -> list[str]:
        return [
            self.handle,
            self.display_name,
            self.sequence,
            self.enrolled_at,
            str(self.current_step),
            self.next_send_at,
            self.last_sent_at,
            self.status,
            self.notes,
        ]


def now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


@_retry_on_quota
def read_all() -> list[Contact]:
    ws = _worksheet()
    values = ws.get_all_values()
    if not values or len(values) < 2:
        return []
    return [Contact.from_row(row, i + 1) for i, row in enumerate(values[1:], start=1)]


@_retry_on_quota
def upsert_contact(c: Contact) -> Contact:
    """Insert a new contact row if (handle, sequence) is new; otherwise return existing."""
    ws = _worksheet()
    existing = read_all()
    for ex in existing:
        if ex.handle == c.handle and ex.sequence == c.sequence:
            return ex
    ws.append_row(c.to_row(), value_input_option="USER_ENTERED")
    # The new row is at len(existing) + 2 (header + 1-based)
    c._row = len(existing) + 2
    return c


@_retry_on_quota
def update_contact(c: Contact) -> None:
    if c._row <= 1:
        raise ValueError("Cannot update a contact without a row index. Read it first.")
    ws = _worksheet()
    ws.update(f"A{c._row}:I{c._row}", [c.to_row()], value_input_option="USER_ENTERED")
