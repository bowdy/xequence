# Workflow: send_pending_dms

## Objective
Send every DM that has come due, advance the state machine, stop early if X starts pushing back. This is the only tool you want to run on a schedule.

## Required inputs
- A valid Playwright session (see `pull_mutuals.md`)
- Sheets env vars (see `enroll_contacts.md`)
- Rate-limit env vars in `.env`: `XEQUENCE_MAX_PER_RUN`, `XEQUENCE_MIN_DELAY_SECONDS`, `XEQUENCE_MAX_DELAY_SECONDS`

## Tool
`tools/send_due_messages.py`

## Steps
1. First time: do a dry run to see what would be sent.
   ```
   python tools/send_due_messages.py --dry-run
   ```
   This prints rendered messages with placeholders filled in. If a message looks wrong, edit the sequence YAML — don't edit the rendered output.
2. Send for real:
   ```
   python tools/send_due_messages.py
   ```
3. Schedule it. Every 30 minutes is plenty for most use cases:
   ```
   */30 * * * * cd /path/to/xequence && /path/to/python tools/send_due_messages.py >> .tmp/tick.log 2>&1
   ```

## State transitions
- `pending` → `in_progress` after step 0 lands
- `in_progress` → `in_progress` after each intermediate step
- `in_progress` → `completed` after the last step lands
- → `stopped` if the DM button disappears (they closed DMs / unfollowed / blocked)
- → `error` on any hard failure; the batch also aborts so we don't burn through the rest

## Rate-limit philosophy
The defaults (max 20 / run, 35–75 second jitter) assume you're running every 30 minutes and want to stay well below X's anti-spam thresholds. If you push these higher you'll see more `error` rows.

## Failure modes seen in the wild
- **`no_dm_button` on every contact in a row**: the session is logged out. Re-run `tools/browser_session.py login`.
- **`send_failed: send button disabled`**: usually a message that violates X's content filter (links to flagged domains, repeated text). Edit the sequence and retry.
- **`send_failed: composer still has the message`**: X intercepted and showed a warning dialog. Run with `--headed` to see what's blocking.

## When to update this workflow
If you tune the rate-limit envs and find sustainable numbers, record them here.
