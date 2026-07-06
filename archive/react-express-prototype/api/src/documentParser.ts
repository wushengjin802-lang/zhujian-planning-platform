import fs from "node:fs/promises";
import path from "node:path";
import mammoth from "mammoth";

export async function extractDocumentText(filePath: string, mimeType?: string) {
  const ext = path.extname(filePath).toLowerCase();
  if (ext === ".docx" || mimeType?.includes("wordprocessingml")) {
    const result = await mammoth.extractRawText({ path: filePath });
    return normalizeText(result.value);
  }

  if ([".txt", ".md", ".csv", ".json", ".xml"].includes(ext) || mimeType?.startsWith("text/")) {
    return normalizeText(await fs.readFile(filePath, "utf8"));
  }

  return "该文件类型已完成元数据登记，正文抽取需接入 OCR/专业解析服务。";
}

export function chunkText(text: string, maxLength = 420) {
  const paragraphs = normalizeText(text)
    .split(/\n+/)
    .map((item) => item.trim())
    .filter(Boolean);
  const chunks: string[] = [];
  let current = "";

  for (const paragraph of paragraphs) {
    if ((current + "\n" + paragraph).trim().length > maxLength && current) {
      chunks.push(current.trim());
      current = paragraph;
    } else {
      current = `${current}\n${paragraph}`.trim();
    }
  }

  if (current) chunks.push(current.trim());
  return chunks.length ? chunks : [normalizeText(text).slice(0, maxLength) || "空白资料"];
}

function normalizeText(text: string) {
  return text.replace(/\r\n/g, "\n").replace(/\t/g, " ").replace(/\n{3,}/g, "\n\n").trim();
}
