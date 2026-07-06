import pg from "pg";
import { config, requireDatabaseUrl } from "../config.js";

const { Client } = pg;
const targetUrl = new URL(requireDatabaseUrl());
const targetDatabase = targetUrl.pathname.replace(/^\//, "");

if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(targetDatabase)) {
  throw new Error(`Unsafe database name: ${targetDatabase}`);
}

const maintenanceUrl = new URL(targetUrl.toString());
maintenanceUrl.pathname = "/postgres";

const client = new Client({
  connectionString: maintenanceUrl.toString(),
  ssl: config.pgSslMode === "require" ? { rejectUnauthorized: false } : undefined
});

try {
  await client.connect();
  const exists = await client.query<{ exists: boolean }>(
    "select exists(select 1 from pg_database where datname = $1) as exists",
    [targetDatabase]
  );
  if (!exists.rows[0]?.exists) {
    await client.query(`create database ${targetDatabase}`);
    console.log(`created database ${targetDatabase}`);
  } else {
    console.log(`database ${targetDatabase} already exists`);
  }
} finally {
  await client.end();
}
