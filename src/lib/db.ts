import Database from "better-sqlite3";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";

const DB_PATH = resolve(process.env.DATABASE_PATH ?? "./data/xequence.db");
mkdirSync(dirname(DB_PATH), { recursive: true });

declare global {
  var __xequence_db: Database.Database | undefined;
}

function open(): Database.Database {
  const db = new Database(DB_PATH);
  db.pragma("journal_mode = WAL");
  db.pragma("foreign_keys = ON");
  migrate(db);
  return db;
}

export const db: Database.Database = globalThis.__xequence_db ?? open();
if (process.env.NODE_ENV !== "production") globalThis.__xequence_db = db;

function migrate(d: Database.Database) {
  d.exec(`
    CREATE TABLE IF NOT EXISTS contacts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      handle TEXT NOT NULL UNIQUE,
      display_name TEXT,
      notes TEXT,
      created_at INTEGER NOT NULL DEFAULT (unixepoch())
    );

    CREATE TABLE IF NOT EXISTS sequences (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      description TEXT,
      created_at INTEGER NOT NULL DEFAULT (unixepoch())
    );

    CREATE TABLE IF NOT EXISTS sequence_steps (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      sequence_id INTEGER NOT NULL REFERENCES sequences(id) ON DELETE CASCADE,
      step_order INTEGER NOT NULL,
      delay_hours INTEGER NOT NULL DEFAULT 0,
      body TEXT NOT NULL,
      UNIQUE (sequence_id, step_order)
    );

    CREATE TABLE IF NOT EXISTS enrollments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
      sequence_id INTEGER NOT NULL REFERENCES sequences(id) ON DELETE CASCADE,
      status TEXT NOT NULL DEFAULT 'active',
      next_step_order INTEGER NOT NULL DEFAULT 1,
      next_run_at INTEGER NOT NULL,
      started_at INTEGER NOT NULL DEFAULT (unixepoch()),
      completed_at INTEGER,
      UNIQUE (contact_id, sequence_id)
    );

    CREATE TABLE IF NOT EXISTS messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      enrollment_id INTEGER NOT NULL REFERENCES enrollments(id) ON DELETE CASCADE,
      step_id INTEGER NOT NULL REFERENCES sequence_steps(id) ON DELETE CASCADE,
      body TEXT NOT NULL,
      status TEXT NOT NULL,
      error TEXT,
      sent_at INTEGER NOT NULL DEFAULT (unixepoch())
    );

    CREATE INDEX IF NOT EXISTS idx_enrollments_due
      ON enrollments(status, next_run_at);
  `);
}

export type Contact = {
  id: number;
  handle: string;
  display_name: string | null;
  notes: string | null;
  created_at: number;
};

export type Sequence = {
  id: number;
  name: string;
  description: string | null;
  created_at: number;
};

export type SequenceStep = {
  id: number;
  sequence_id: number;
  step_order: number;
  delay_hours: number;
  body: string;
};

export type Enrollment = {
  id: number;
  contact_id: number;
  sequence_id: number;
  status: "active" | "completed" | "paused" | "failed";
  next_step_order: number;
  next_run_at: number;
  started_at: number;
  completed_at: number | null;
};

export type Message = {
  id: number;
  enrollment_id: number;
  step_id: number;
  body: string;
  status: "sent" | "failed";
  error: string | null;
  sent_at: number;
};
