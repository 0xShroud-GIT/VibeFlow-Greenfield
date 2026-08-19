import { drizzle, type NodePgDatabase } from "drizzle-orm/node-postgres";
import pg from "pg";

import { CONTROL_PLANE_TABLES } from "./schema.js";

export type ControlPlaneDatabase = NodePgDatabase<typeof CONTROL_PLANE_TABLES>;

export interface ControlPlanePool {
  readonly pool: pg.Pool;
  readonly db: ControlPlaneDatabase;
  close(): Promise<void>;
}

export function createControlPlanePool(connectionString: string): ControlPlanePool {
  const pool = new pg.Pool({ connectionString });
  const db = drizzle(pool, { schema: CONTROL_PLANE_TABLES });
  return {
    pool,
    db,
    async close() {
      await pool.end();
    },
  };
}
