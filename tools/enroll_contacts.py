"""
Enroll a list of handles into a sequence.

Reads handles from a file (one per line, with or without @) and appends each
to the Google Sheet with status=pending and next_send_at=now (so the first
step fires the next time send_due_messages.py runs).

Usage:
    python tools/enroll_contacts.py --file .tmp/mutuals.txt
    python tools/enroll_contacts.py --file shortlist.txt --sequence default
    python tools/enroll_contacts.py --handles alice,bob,carol --sequence default
"""
from __future__ import annotations

from pathlib import Path

import click

from tools.sequences import load_sequence, schedule_for_step
from tools.sheets_client import Contact, now_iso, read_all, upsert_contact
from datetime import datetime, timezone


def _parse_input(file: str | None, handles: str | None) -> list[str]:
    out: list[str] = []
    if file:
        text = Path(file).read_text()
        out.extend(line.strip().lstrip("@").lower() for line in text.splitlines() if line.strip())
    if handles:
        out.extend(h.strip().lstrip("@").lower() for h in handles.split(",") if h.strip())
    # De-dup while preserving order
    seen = set()
    deduped = []
    for h in out:
        if h not in seen:
            seen.add(h)
            deduped.append(h)
    return deduped


@click.command()
@click.option("--file", "file", default=None, help="Newline-delimited handles file.")
@click.option("--handles", "handles", default=None, help="Comma-separated handles.")
@click.option("--sequence", "sequence", default="default", help="Sequence name (matches sequences/<name>.yaml).")
def main(file: str | None, handles: str | None, sequence: str) -> None:
    if not file and not handles:
        raise click.UsageError("Pass --file or --handles")

    seq = load_sequence(sequence)
    new_handles = _parse_input(file, handles)
    click.echo(f"Enrolling {len(new_handles)} handles into sequence '{sequence}'…")

    existing = {(c.handle, c.sequence) for c in read_all()}
    enrolled_at = datetime.now(tz=timezone.utc).replace(microsecond=0)
    first_send = schedule_for_step(enrolled_at, seq.steps[0])

    added = 0
    skipped = 0
    for handle in new_handles:
        key = (handle, sequence)
        if key in existing:
            skipped += 1
            continue
        c = Contact(
            handle=handle,
            sequence=sequence,
            enrolled_at=enrolled_at.isoformat(),
            current_step=0,
            next_send_at=first_send.isoformat(),
            status="pending",
        )
        upsert_contact(c)
        added += 1

    click.echo(f"Done. Added {added}, skipped {skipped} already enrolled.")


if __name__ == "__main__":
    main()
