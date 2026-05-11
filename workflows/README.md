# Workflows

These are the SOPs the agent (Claude) follows. Each one names the tool to run, what inputs it needs, and what to do if something breaks. If you discover a better way to do something, update the workflow — they're meant to evolve.

## End-to-end flow

```
1. pull_mutuals.md         → scrape your X mutuals → .tmp/mutuals.txt
2. enroll_contacts.md      → push handles into the state Sheet → status=pending
3. send_pending_dms.md     → run on a schedule → fires step messages as they come due
```

Each step is idempotent: re-running pull_mutuals overwrites the file; re-running enroll skips already-enrolled handles; re-running send only acts on contacts whose `next_send_at` has passed.
