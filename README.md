# Xequence

Self-hosted DM sequences for Twitter/X. Build mini multi-step outreach flows for
your connections, time-delayed step by step, with the sending happening through
a Playwright-driven browser session you control.

> **Heads-up:** automating DMs against the public X web UI is against the X
> Terms of Service and can get your account suspended. Use this on accounts you
> own, with people who know you, and with sensible rate limits. You are
> responsible for how you use it.

## Stack

- Next.js (App Router) + TypeScript for the UI and server actions
- SQLite (`better-sqlite3`) for storage — a single file under `./data/`
- Playwright (Chromium) with a persistent profile for the X session
- A standalone worker process that polls the queue and sends due messages

## Setup

```bash
npm install
npx playwright install chromium
cp .env.example .env
```

## One-time login

Open a browser, log in to X manually, then close the window. Cookies persist in
`./playwright-profile/` and the worker reuses them.

```bash
npm run login
```

## Run

In two terminals:

```bash
# UI on http://localhost:3000
npm run dev

# Sender — polls every 30s for due steps
npm run worker
```

## Usage

1. **Contacts** — add the people you want to message. Handles only (no `@`).
2. **Sequences** — create a sequence, then add steps. Each step has a delay (in
   hours) measured from the previous step (or from enrollment, for step 1) and a
   message body. Use `{{ name }}` or `{{ handle }}` for personalization.
3. **Sequences → detail** — enroll a contact. They get the first step after its
   configured delay; the worker advances them through the rest automatically.
4. **Enrollments** — pause, resume, or remove anyone mid-sequence.
5. **Messages** — audit log of every send (and every failure).

## Schema

- `contacts` (handle, display_name, notes)
- `sequences` (name, description)
- `sequence_steps` (sequence_id, step_order, delay_hours, body)
- `enrollments` (contact_id, sequence_id, status, next_step_order, next_run_at)
- `messages` (enrollment_id, step_id, body, status, error, sent_at)

## Environment

| var | default | description |
| --- | --- | --- |
| `DATABASE_PATH` | `./data/xequence.db` | SQLite file location |
| `PLAYWRIGHT_PROFILE` | `./playwright-profile` | Persistent browser profile |
| `PLAYWRIGHT_HEADED` | `true` | Show the sending browser |
| `WORKER_INTERVAL_SECONDS` | `30` | Poll cadence |
| `SEND_JITTER_MS` | `4000` | Min jittered delay between sends (jitter up to 2x) |

## Notes & caveats

- The sender uses X's `data-testid` selectors. X tweaks markup periodically; if
  sending breaks, update the selectors in `src/lib/twitter.ts`.
- Only one worker should run at a time against a given profile.
- There is no reply detection yet. Steps fire on schedule regardless of whether
  the recipient replied. Add a check before sending if that matters to you.
