import { db } from "../lib/db";
import { contacts, enrollments, messages, renderTemplate, sequences } from "../lib/repo";
import { isLoggedIn, jitterDelay, launchContext, sendDirectMessage } from "../lib/twitter";

const INTERVAL_S = Number(process.env.WORKER_INTERVAL_SECONDS ?? 30);
const JITTER_MS = Number(process.env.SEND_JITTER_MS ?? 4000);

async function tick() {
  const now = Math.floor(Date.now() / 1000);
  const due = enrollments.due(now);
  if (due.length === 0) return;

  console.log(`[worker] ${due.length} due enrollment(s)`);
  const ctx = await launchContext();
  const page = await ctx.newPage();
  try {
    if (!(await isLoggedIn(page))) {
      console.error("[worker] not logged in to X. Run `npm run login` first.");
      return;
    }

    for (const e of due) {
      const contact = contacts.get(e.contact_id);
      if (!contact) {
        enrollments.fail(e.id);
        continue;
      }
      const step = db
        .prepare(
          "SELECT * FROM sequence_steps WHERE sequence_id = ? AND step_order = ?",
        )
        .get(e.sequence_id, e.next_step_order) as
        | { id: number; body: string; step_order: number }
        | undefined;
      if (!step) {
        enrollments.fail(e.id);
        continue;
      }

      const body = renderTemplate(step.body, contact);
      try {
        console.log(`[worker] -> @${contact.handle} step ${step.step_order}`);
        await sendDirectMessage(page, contact.handle, body);
        messages.log(e.id, step.id, body, "sent");
        enrollments.advance(e.id, e.sequence_id, step.step_order);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        console.error(`[worker] failed @${contact.handle}: ${msg}`);
        messages.log(e.id, step.id, body, "failed", msg);
        enrollments.fail(e.id);
      }
      await jitterDelay(JITTER_MS);
    }
  } finally {
    await ctx.close();
  }
}

async function main() {
  // Touch repo so schema migrates.
  sequences.list();
  console.log(`[worker] starting, polling every ${INTERVAL_S}s`);
  let running = false;
  const loop = async () => {
    if (running) return;
    running = true;
    try {
      await tick();
    } catch (e) {
      console.error("[worker] tick error", e);
    } finally {
      running = false;
    }
  };
  await loop();
  setInterval(loop, INTERVAL_S * 1000);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
