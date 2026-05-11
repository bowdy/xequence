"""
Scrape your mutual follows on X and write them to .tmp/mutuals.txt.

Usage:
    python tools/pull_mutuals.py
    python tools/pull_mutuals.py --output path/to/file.txt
    python tools/pull_mutuals.py --headed     # show the browser, useful for debugging

The output file is plain text, one handle per line, no @. Feed it into
`enroll_contacts.py` to actually start a sequence.
"""
from __future__ import annotations

from pathlib import Path

import click

from tools._common import REPO_ROOT, env
from tools.browser_session import x_session
from tools.twitter_client import fetch_mutuals


@click.command()
@click.option("--output", "output", default=None, help="Output file path. Defaults to .tmp/mutuals.txt.")
@click.option("--headed", is_flag=True, help="Show the browser window (debugging).")
def main(output: str | None, headed: bool) -> None:
    handle = env("X_HANDLE", required=True).lstrip("@")
    out_p = Path(output) if output else REPO_ROOT / ".tmp" / "mutuals.txt"
    out_p.parent.mkdir(parents=True, exist_ok=True)

    click.echo(f"Fetching mutuals for @{handle} (this scrolls two long lists — give it a minute)…")
    with x_session(headless=not headed) as (_ctx, page):
        mutuals = fetch_mutuals(page, handle)

    out_p.write_text("\n".join(mutuals) + "\n")
    click.echo(f"Wrote {len(mutuals)} mutuals to {out_p}")


if __name__ == "__main__":
    main()
