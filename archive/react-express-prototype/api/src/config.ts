import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";

const currentFile = fileURLToPath(import.meta.url);
const apiRoot = path.resolve(path.dirname(currentFile), "..");
const workspaceRoot = path.resolve(apiRoot, "..", "..");

dotenv.config({ path: path.join(workspaceRoot, ".env") });
dotenv.config();

export const config = {
  port: Number(process.env.PORT ?? 8787),
  databaseUrl: process.env.DATABASE_URL,
  pgSchema: process.env.PGSCHEMA ?? "zhujian_mvp",
  pgSslMode: process.env.PGSSLMODE ?? "disable",
  workspaceRoot
};

export function requireDatabaseUrl() {
  if (!config.databaseUrl) {
    throw new Error("DATABASE_URL is required. Copy .env.example to .env and fill the PostgreSQL connection string.");
  }
  return config.databaseUrl;
}
