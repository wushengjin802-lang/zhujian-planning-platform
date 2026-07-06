import { config } from "../config.js";
import { closePool, pool } from "../db/pool.js";

try {
  const result = await pool.query<{ now: string; current_database: string }>(
    "select now()::text, current_database()::text"
  );
  console.log(JSON.stringify({ ok: true, schema: config.pgSchema, ...result.rows[0] }, null, 2));
} finally {
  await closePool();
}
