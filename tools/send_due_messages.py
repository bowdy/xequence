"""
The "tick" runner. Looks at the state sheet, finds contacts whose
next_send_at has passed, sends the next step of their sequence, and advances
them. Stop conditions:

  - hits XEQUENCE_MAX_PER_RUN (default 20)
  - encounters a hard failure (likely shadow-ban / rate-limit) — bails the
    whole batch so you don't keep hammering X

Run on cron / launchd / any scheduler:
    */30 * * * * cd /path/to/xequence && python tools/send_due_messages.py >> .tmp/tick.log 2>&1
"""
from __future__ import annotations

import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import click  # noqa: E402

from tools._common import env  # noqa: E402
from tools.browser_session import x_session  # noqa: E402
from tools.sequences import (  # noqa: E402
    load_sequence,
    parse_iso,
    render,
    schedule_for_step,
)
from tools.sheets_client import Contact, now_iso, read_all, update_contact  # noqa: E402
from tools.twitter_client import fetch_display_name, send_dm  # noqa: E402


def _due(contact: Contact, now: datetime) -> bool:
    if contact.status not in ("pending", "in_progress"):
        return False
    if not contact.next_send_at:
        return False
    try:
        return parse_iso(contact.next_send_at) <= now
    except ValueError:
        return False


@click.command()
@click.option("--dry-run", is_flag=True, help="Print what would be sent without touching X.")
@click.option("--headed", is_flag=True, help="Show the browser window (debugging).")
@click.option("--limit", type=int, default=None, help="Override XEQUENCE_MAX_PER_RUN.")
def main(dry_run: bool, headed: bool, limit: int | None) -> None:
    max_per_run = limit or int(env("XEQUENCE_MAX_PER_RUN", "20"))
    min_delay = int(env("XEQUENCE_MIN_DELAY_SECONDS", "35"))
    max_delay = int(env("XEQUENCE_MAX_DELAY_SECONDS", "75"))

    now = datetime.now(tz=timezone.utc)
    contacts = read_all()
    due = [c for c in contacts if _due(c, now)]
    click.echo(f"{len(due)} contacts are due (of {len(contacts)} total). Will send up to {max_per_run}.")

    if not due:
        return

    # Group by sequence so we only load each YAML once.
    seq_cache: dict[str, object] = {}

    def seq(name: str):
        if name not in seq_cache:
            seq_cache[name] = load_sequence(name)
        return seq_cache[name]

    if dry_run:
        for c in due[:max_per_run]:
            s = seq(c.sequence)
            step = s.steps[c.current_step] if c.current_step < len(s.steps) else None
            preview = render(step.message, handle=c.handle, display_name=c.display_name) if step else "(no step)"
            click.echo(f"\n--- @{c.handle} (step {c.current_step}) ---\n{preview}")
        return

    sent = 0
    with x_session(headless=not headed) as (_ctx, page):
        for c in due:
            if sent >= max_per_run:
                click.echo(f"Hit per-run cap ({max_per_run}). Stopping.")
                break

            s = seq(c.sequence)
            if c.current_step >= len(s.steps):
                c.status = "completed"
                c.notes = "all steps completed"
                update_contact(c)
                continue

            step = s.steps[c.current_step]

            # Lazy-fetch display name on the first send only.
            if not c.display_name:
                name = fetch_display_name(page, c.handle)
                if name:
                    c.display_name = name

            message = render(step.message, handle=c.handle, display_name=c.display_name)
            click.echo(f"→ @{c.handle} (step {c.current_step})")
            result = send_dm(page, c.handle, message)

            if result.status == "sent":
                c.last_sent_at = now_iso()
                c.current_step += 1
                if c.current_step >= len(s.steps):
                    c.status = "completed"
                    c.next_send_at = ""
                else:
                    enrolled = parse_iso(c.enrolled_at) if c.enrolled_at else datetime.now(tz=timezone.utc)
                    next_step = s.steps[c.current_step]
                    c.next_send_at = schedule_for_step(enrolled, next_step).isoformat()
                    c.status = "in_progress"
                c.notes = ""
                update_contact(c)
                sent += 1

                if sent < max_per_run:
                    delay = random.uniform(min_delay, max_delay)
                    click.echo(f"  sent. sleeping {delay:.1f}s…")
                    time.sleep(delay)

            elif result.status == "no_dm_button":
                # Not a hard failure — they may have closed DMs or unfollowed.
                c.status = "stopped"
                c.notes = f"{result.status}: {result.detail}"
                update_contact(c)
                click.echo(f"  skip: {result.status}")

            else:
                # send_failed / navigation_failed / blocked → record and bail.
                # Bailing early protects the account when X starts rejecting us.
                c.notes = f"{result.status}: {result.detail}"
                c.status = "error"
                update_contact(c)
                click.echo(f"  hard failure: {result.status} — {result.detail}. Stopping the batch.")
                break

    click.echo(f"Done. Sent {sent} this run.")


if __name__ == "__main__":
    main()
