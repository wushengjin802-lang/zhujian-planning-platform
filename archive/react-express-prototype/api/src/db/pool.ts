import pg from "pg";
import { config, requireDatabaseUrl } from "../config.js";

const { Pool } = pg;

export const pool = new Pool({
  connectionString: requireDatabaseUrl(),
  ssl: config.pgSslMode === "require" ? { rejectUnauthorized: false } : undefined,
  options: `-c search_path=${config.pgSchema},public`
});

export async function closePool() {
  await pool.end();
}
