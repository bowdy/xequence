# Workflow: enroll_contacts

## Objective
Add a list of handles to the Google Sheet so they enter a sequence. Each enrollment schedules step 0 to fire on the next tick.

## Required inputs
- A handles source — either:
  - a newline-delimited file (e.g. `.tmp/mutuals.txt` from `pull_mutuals`), or
  - a comma-separated list passed inline
- The sequence name — must match a file in `sequences/<name>.yaml` (defaults to `default`)
- Google Sheets env vars: `GOOGLE_SERVICE_ACCOUNT_JSON`, `XEQUENCE_SHEET_ID`, `XEQUENCE_SHEET_TAB`
- The service account email must be added as an **editor** on the target Sheet

## Tool
`tools/enroll_contacts.py`

## Steps
1. Confirm the sequence you intend to enroll into exists at `sequences/<name>.yaml`. The repo ships with `sequences/default.yaml` — copy it to `sequences/<your-name>.yaml` and edit if you want a new one.
2. If enrolling from the full mutuals dump, **review the list first** — this is the audience for an automated DM, so curating it now prevents regret later. Save the curated subset to e.g. `.tmp/shortlist.txt`.
3. Run:
   ```
   python tools/enroll_contacts.py --file .tmp/shortlist.txt --sequence default
   ```
4. The tool prints how many were added and how many were skipped as already-enrolled. Re-running is safe; nobody gets double-enrolled in the same sequence.

## Outputs
- Appended rows in the Google Sheet, one per (handle, sequence) pair, with `status=pending` and `next_send_at` set to step 0's due time.

## Failure modes seen in the wild
- **PermissionError opening the sheet**: the service account isn't shared on the Sheet. Open the Sheet → Share → paste the `client_email` from the service account JSON.
- **`FileNotFoundError` on the sequence**: typo in `--sequence`. Filename and value must match exactly.
