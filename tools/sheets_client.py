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
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

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


def _client() -> gspread.Client:
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
    return gspread.authorize(creds)


def _worksheet() -> gspread.Worksheet:
    sh_id = _extract_sheet_id(env("XEQUENCE_SHEET_ID", required=True))
    tab = env("XEQUENCE_SHEET_TAB", "contacts")
    sh = _client().open_by_key(sh_id)
    try:
        ws = sh.worksheet(tab)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab, rows=1000, cols=len(HEADERS))
    # Idempotent header ensure
    first_row = ws.row_values(1)
    if first_row != HEADERS:
        ws.update("A1", [HEADERS])
    return ws


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


def read_all() -> list[Contact]:
    ws = _worksheet()
    values = ws.get_all_values()
    if not values or len(values) < 2:
        return []
    return [Contact.from_row(row, i + 1) for i, row in enumerate(values[1:], start=1)]


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


def update_contact(c: Contact) -> None:
    if c._row <= 1:
        raise ValueError("Cannot update a contact without a row index. Read it first.")
    ws = _worksheet()
    ws.update(f"A{c._row}:I{c._row}", [c.to_row()], value_input_option="USER_ENTERED")
