import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import type pg from "pg";

const DEFAULT_MIGRATIONS_DIR = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../migrations",
);

export function defaultMigrationsDirectory(): string {
  return DEFAULT_MIGRATIONS_DIR;
}

export async function listCommittedSqlMigrations(migrationsDir = DEFAULT_MIGRATIONS_DIR): Promise<string[]> {
  const entries = await readdir(migrationsDir);
  return entries.filter((name) => /^\d{4}_.+\.sql$/.test(name)).sort();
}

export async function applyCommittedSqlMigrations(
  pool: pg.Pool,
  migrationsDir = DEFAULT_MIGRATIONS_DIR,
): Promise<{ applied: string[]; skipped: string[] }> {
  const files = await listCommittedSqlMigrations(migrationsDir);
  const applied: string[] = [];
  const skipped: string[] = [];

  await pool.query(`
    CREATE TABLE IF NOT EXISTS vibeflow_schema_migrations (
      id text PRIMARY KEY,
      applied_at timestamptz NOT NULL DEFAULT now()
    )
  `);

  for (const file of files) {
    const existing = await pool.query<{ id: string }>(
      "SELECT id FROM vibeflow_schema_migrations WHERE id = $1",
      [file],
    );
    if ((existing.rowCount ?? existing.rows.length) > 0) {
      skipped.push(file);
      continue;
    }

    const sql = await readFile(path.join(migrationsDir, file), "utf8");
    const client = await pool.connect();
    try {
      await client.query("BEGIN");
      await client.query(sql);
      await client.query("INSERT INTO vibeflow_schema_migrations (id) VALUES ($1)", [file]);
      await client.query("COMMIT");
      applied.push(file);
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
  }

  return { applied, skipped };
}
