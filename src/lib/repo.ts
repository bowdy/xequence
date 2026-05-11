import { db, type Contact, type Enrollment, type Sequence, type SequenceStep } from "./db";

export const contacts = {
  list(): Contact[] {
    return db.prepare("SELECT * FROM contacts ORDER BY created_at DESC").all() as Contact[];
  },
  get(id: number): Contact | undefined {
    return db.prepare("SELECT * FROM contacts WHERE id = ?").get(id) as Contact | undefined;
  },
  create(handle: string, display_name?: string, notes?: string): Contact {
    const clean = handle.replace(/^@/, "").trim();
    const info = db
      .prepare(
        "INSERT INTO contacts (handle, display_name, notes) VALUES (?, ?, ?) ON CONFLICT(handle) DO UPDATE SET display_name = excluded.display_name, notes = excluded.notes RETURNING *",
      )
      .get(clean, display_name ?? null, notes ?? null) as Contact;
    return info;
  },
  delete(id: number): void {
    db.prepare("DELETE FROM contacts WHERE id = ?").run(id);
  },
};

export const sequences = {
  list(): Sequence[] {
    return db.prepare("SELECT * FROM sequences ORDER BY created_at DESC").all() as Sequence[];
  },
  get(id: number): Sequence | undefined {
    return db.prepare("SELECT * FROM sequences WHERE id = ?").get(id) as Sequence | undefined;
  },
  create(name: string, description?: string): Sequence {
    return db
      .prepare("INSERT INTO sequences (name, description) VALUES (?, ?) RETURNING *")
      .get(name, description ?? null) as Sequence;
  },
  delete(id: number): void {
    db.prepare("DELETE FROM sequences WHERE id = ?").run(id);
  },
  steps(sequence_id: number): SequenceStep[] {
    return db
      .prepare("SELECT * FROM sequence_steps WHERE sequence_id = ? ORDER BY step_order ASC")
      .all(sequence_id) as SequenceStep[];
  },
  replaceSteps(sequence_id: number, steps: Array<{ delay_hours: number; body: string }>): void {
    const tx = db.transaction((items: Array<{ delay_hours: number; body: string }>) => {
      db.prepare("DELETE FROM sequence_steps WHERE sequence_id = ?").run(sequence_id);
      const ins = db.prepare(
        "INSERT INTO sequence_steps (sequence_id, step_order, delay_hours, body) VALUES (?, ?, ?, ?)",
      );
      items.forEach((s, i) => ins.run(sequence_id, i + 1, s.delay_hours, s.body));
    });
    tx(steps);
  },
};

export const enrollments = {
  list(): Array<Enrollment & { handle: string; sequence_name: string }> {
    return db
      .prepare(
        `SELECT e.*, c.handle AS handle, s.name AS sequence_name
         FROM enrollments e
         JOIN contacts c ON c.id = e.contact_id
         JOIN sequences s ON s.id = e.sequence_id
         ORDER BY e.next_run_at ASC`,
      )
      .all() as Array<Enrollment & { handle: string; sequence_name: string }>;
  },
  enroll(contact_id: number, sequence_id: number): Enrollment {
    const firstStep = db
      .prepare(
        "SELECT * FROM sequence_steps WHERE sequence_id = ? ORDER BY step_order ASC LIMIT 1",
      )
      .get(sequence_id) as SequenceStep | undefined;
    if (!firstStep) throw new Error("Sequence has no steps");
    const next_run_at = Math.floor(Date.now() / 1000) + firstStep.delay_hours * 3600;
    return db
      .prepare(
        `INSERT INTO enrollments (contact_id, sequence_id, next_step_order, next_run_at)
         VALUES (?, ?, 1, ?)
         ON CONFLICT(contact_id, sequence_id)
         DO UPDATE SET status = 'active', next_step_order = 1, next_run_at = excluded.next_run_at, completed_at = NULL
         RETURNING *`,
      )
      .get(contact_id, sequence_id, next_run_at) as Enrollment;
  },
  pause(id: number): void {
    db.prepare("UPDATE enrollments SET status = 'paused' WHERE id = ?").run(id);
  },
  resume(id: number): void {
    db.prepare(
      "UPDATE enrollments SET status = 'active', next_run_at = unixepoch() WHERE id = ?",
    ).run(id);
  },
  delete(id: number): void {
    db.prepare("DELETE FROM enrollments WHERE id = ?").run(id);
  },
  due(now: number): Enrollment[] {
    return db
      .prepare(
        "SELECT * FROM enrollments WHERE status = 'active' AND next_run_at <= ? ORDER BY next_run_at ASC",
      )
      .all(now) as Enrollment[];
  },
  advance(id: number, sequence_id: number, completed_step_order: number): void {
    const nextStep = db
      .prepare(
        "SELECT * FROM sequence_steps WHERE sequence_id = ? AND step_order > ? ORDER BY step_order ASC LIMIT 1",
      )
      .get(sequence_id, completed_step_order) as SequenceStep | undefined;
    if (!nextStep) {
      db.prepare(
        "UPDATE enrollments SET status = 'completed', completed_at = unixepoch() WHERE id = ?",
      ).run(id);
      return;
    }
    const next_run_at = Math.floor(Date.now() / 1000) + nextStep.delay_hours * 3600;
    db.prepare(
      "UPDATE enrollments SET next_step_order = ?, next_run_at = ? WHERE id = ?",
    ).run(nextStep.step_order, next_run_at, id);
  },
  fail(id: number): void {
    db.prepare("UPDATE enrollments SET status = 'failed' WHERE id = ?").run(id);
  },
};

export const messages = {
  log(
    enrollment_id: number,
    step_id: number,
    body: string,
    status: "sent" | "failed",
    error?: string,
  ): void {
    db.prepare(
      "INSERT INTO messages (enrollment_id, step_id, body, status, error) VALUES (?, ?, ?, ?, ?)",
    ).run(enrollment_id, step_id, body, status, error ?? null);
  },
  forEnrollment(enrollment_id: number) {
    return db
      .prepare("SELECT * FROM messages WHERE enrollment_id = ? ORDER BY sent_at DESC")
      .all(enrollment_id);
  },
  recent(limit = 50) {
    return db
      .prepare(
        `SELECT m.*, c.handle AS handle
         FROM messages m
         JOIN enrollments e ON e.id = m.enrollment_id
         JOIN contacts c ON c.id = e.contact_id
         ORDER BY m.sent_at DESC LIMIT ?`,
      )
      .all(limit);
  },
};

export function renderTemplate(body: string, contact: Contact): string {
  return body
    .replace(/\{\{\s*handle\s*\}\}/g, contact.handle)
    .replace(/\{\{\s*name\s*\}\}/g, contact.display_name || contact.handle);
}
