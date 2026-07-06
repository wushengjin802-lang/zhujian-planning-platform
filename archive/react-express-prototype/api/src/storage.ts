import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { config } from "./config.js";

export const storageRoot = path.join(config.workspaceRoot, "storage");
export const uploadRoot = path.join(storageRoot, "documents");
export const artifactRoot = path.join(storageRoot, "artifacts");

export async function ensureStorageDirs() {
  await fs.mkdir(uploadRoot, { recursive: true });
  await fs.mkdir(artifactRoot, { recursive: true });
}

export async function checksumFile(filePath: string) {
  const hash = crypto.createHash("sha256");
  const buffer = await fs.readFile(filePath);
  hash.update(buffer);
  return hash.digest("hex");
}

export function safeStoragePath(filePath: string) {
  const resolved = path.resolve(filePath);
  const root = path.resolve(storageRoot);
  if (!resolved.startsWith(root)) {
    throw new Error("Storage path is outside configured storage root");
  }
  return resolved;
}

export async function writeArtifactFile(name: string, content: string) {
  await ensureStorageDirs();
  const safeName = name.replace(/[\\/:*?"<>|]/g, "_");
  const filePath = path.join(artifactRoot, `${Date.now()}-${safeName}`);
  await fs.writeFile(filePath, content, "utf8");
  const stat = await fs.stat(filePath);
  return {
    storagePath: filePath,
    fileSize: stat.size,
    mimeType: "text/plain; charset=utf-8"
  };
}
