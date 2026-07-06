import fs from "node:fs/promises";
import path from "node:path";
import { config } from "../config.js";
import { closePool, pool } from "../db/pool.js";

const migrationDir = path.join(config.workspaceRoot, "infra", "database", "migrations");
const files = (await fs.readdir(migrationDir)).filter((file) => file.endsWith(".sql")).sort();

try {
  for (const file of files) {
    const sql = await fs.readFile(path.join(migrationDir, file), "utf8");
    await pool.query(sql);
    console.log(`applied ${file}`);
  }
} finally {
  await closePool();
}
