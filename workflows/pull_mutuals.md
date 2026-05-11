# Workflow: pull_mutuals

## Objective
Build a fresh list of accounts you mutually follow on X, written to `.tmp/mutuals.txt` one handle per line.

## Required inputs
- `X_HANDLE` set in `.env` (your X username without the @)
- A valid Playwright session — `tools/browser_session.py login` must have been run at least once

## Tool
`tools/pull_mutuals.py`

## Steps
1. Verify the session works: `python tools/browser_session.py check`. If it fails, run `python tools/browser_session.py login` and ask the user to log in by hand.
2. Run `python tools/pull_mutuals.py`. Expect this to take several minutes for accounts with thousands of follows — both /following and /followers have to be fully scrolled.
3. Sanity-check the count. If it's wildly off from what the user expects, run again with `--headed` to watch the scroll behavior; X sometimes renders truncated lists when it suspects automation.

## Outputs
- `.tmp/mutuals.txt` — newline-delimited handles (no @)

## Failure modes seen in the wild
- **Empty file**: most often a session that's expired. Re-run login.
- **Half-empty**: X throttled the virtual list. Wait an hour and rerun.
- **Wrong handles**: you ran it against the wrong account. Check `X_HANDLE`.

## When to update this workflow
If you find a faster route (e.g. an authenticated GraphQL endpoint), document the new approach here and update the tool, but keep the scroll fallback for when GraphQL responses change shape.
