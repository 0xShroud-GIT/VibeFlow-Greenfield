import { drizzle, type NodePgDatabase } from "drizzle-orm/node-postgres";
import pg from "pg";

import { TENANT_TABLES } from "./schema.js";

export type ControlPlaneDatabase = NodePgDatabase<typeof TENANT_TABLES>;

export interface ControlPlanePool {
  readonly pool: pg.Pool;
  readonly db: ControlPlaneDatabase;
  close(): Promise<void>;
}

export function createControlPlanePool(connectionString: string): ControlPlanePool {
  const pool = new pg.Pool({ connectionString });
  const db = drizzle(pool, { schema: TENANT_TABLES });
  return {
    pool,
    db,
    async close() {
      await pool.end();
    },
  };
}
