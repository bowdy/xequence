# Xequence

Time-based DM sequences for X (Twitter), driven by a Google Sheet and a real logged-in browser.

```
sequences/default.yaml ──┐
                         │
.tmp/mutuals.txt ───────►├── enroll ──► Google Sheet (state) ──► tick ──► X DMs
                         │
your X session cookie ───┘
```

## What this is

- You pull your **mutual follows** on X into a list.
- You curate that list and **enroll** the handles you actually want to reach into a sequence.
- A **sequence** is a YAML file with N steps, each fired some number of days after enrollment (e.g. day 0 / day 3 / day 7).
- A scheduled **tick** sends the next due message for every enrolled contact, paces the sends, advances the state machine, and stops early if X starts pushing back.

All state lives in a Google Sheet so you can watch it, edit it, or rip rows out by hand.

## What this isn't

Not compliant with X's TOS. Driving a logged-in browser to send DMs at scale violates the Developer Agreement. Use a **secondary account** you can afford to lose, keep volume modest, and treat any suspension as expected, not surprising. The official X API supports DMs but only on paid tiers and only to followers — if that fits your use case, build on the API instead.

## Setup

### 1. Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

### 2. Google Sheets credentials

- In Google Cloud Console: create a service account, download its JSON key, save it as `service_account.json` in the project root.
- Create a fresh Google Sheet for state.
- Share the Sheet with the service account's `client_email` (Editor).
- Copy the Sheet's ID (the long string in the URL) into `.env`.

### 3. Configure

```bash
cp .env.example .env
# Edit .env: set X_HANDLE, XEQUENCE_SHEET_ID, paths
```

### 4. Log in to X (one-time)

```bash
python tools/browser_session.py login
```

A real Chromium window opens. Log in by hand — including 2FA. Press Enter in the terminal when you see your home timeline. Your session is saved and reused on every later run.

Verify:
```bash
python tools/browser_session.py check
```

## Usage

You can drive Xequence two ways. They share the same state (the Sheet), so mixing is fine.

### Option A: Web UI (recommended)

```bash
python -m webapp
```

Open http://127.0.0.1:8000. You get:

- A session-status badge in the header (refreshes every 30s).
- A **Pull mutuals** button — scrolls /following + /followers in the background and shows a live log.
- An **Enroll** form — paste handles, pick a sequence, click Enroll.
- A **Tick** panel with a dry-run preview and a "Send now" confirm.
- A contacts table that auto-refreshes from the Sheet every 15s.
- A sequences editor — edit YAML in the browser, saves are validated before disk.

The UI is HTMX + Jinja2 server-rendered. No build step. Everything runs in one Python process on localhost.

### Option B: CLI

Same operations, scriptable. Useful for `cron` / `launchd`.

#### Pull your mutuals

```bash
python tools/pull_mutuals.py
# → writes .tmp/mutuals.txt
```

This scrolls /following and /followers to completion and intersects them. Slow but reliable. Use `--headed` to watch.

#### Enroll handles into a sequence

Curate `.tmp/mutuals.txt` down to the people you actually want to reach (save as `.tmp/shortlist.txt`), then:

```bash
python tools/enroll_contacts.py --file .tmp/shortlist.txt --sequence default
```

Already-enrolled handles are skipped, so re-running is safe.

#### Run the tick (sends due messages)

Dry run to see what's queued:
```bash
python tools/send_due_messages.py --dry-run
```

Real run:
```bash
python tools/send_due_messages.py
```

Schedule it via cron / launchd. Every 30 minutes is plenty:
```cron
*/30 * * * * cd /path/to/xequence && /path/to/.venv/bin/python tools/send_due_messages.py >> .tmp/tick.log 2>&1
```

## Sequences

A sequence is a YAML file in `sequences/`:

```yaml
name: default
steps:
  - day_offset: 0
    message: "hey {first_name} — saw we connected. what are you working on?"
  - day_offset: 3
    message: "ping in case my last note got buried."
  - day_offset: 7
    message: "one last hello — drop me a line if interested."
```

Variables: `{first_name}`, `{display_name}`, `{handle}`. `day_offset` is days from enrollment. Step 0 fires immediately on enroll.

You can have multiple sequences — pass `--sequence <name>` when enrolling.

## State (the Google Sheet)

| handle | display_name | sequence | enrolled_at | current_step | next_send_at | last_sent_at | status | notes |
|--------|--------------|----------|-------------|--------------|--------------|--------------|--------|-------|
| jane   | Jane Doe     | default  | 2026-05-11T… | 1            | 2026-05-14T…  | 2026-05-11T…  | in_progress | |

Status values: `pending`, `in_progress`, `completed`, `error`, `stopped`. You can edit any row by hand — the tick re-reads on every run.

## Project layout

```
sequences/         YAML sequence definitions you author
tools/             deterministic Python scripts (the W in WAT)
workflows/         markdown SOPs Claude follows (the W in WAT)
webapp/            local FastAPI + HTMX UI (run with `python -m webapp`)
.tmp/              scratch space (mutuals dumps, tick logs)
.env               your secrets — never commit
```

## Account-safety knobs

In `.env`:

- `XEQUENCE_MAX_PER_RUN` — hard cap per tick (default 20)
- `XEQUENCE_MIN_DELAY_SECONDS` / `XEQUENCE_MAX_DELAY_SECONDS` — random jitter between sends (default 35–75s)

If you start seeing rows flip to `error`, lower these and slow down. The tool already bails the whole batch on the first hard failure to limit blast radius.
