import fs from "node:fs/promises";
import path from "node:path";
import { Document, Packer, Paragraph, TextRun } from "docx";
import JSZip from "jszip";
import * as XLSX from "xlsx";
import type { Artifact, FactItem, Project, QualityIssue, ReportChapter } from "@zhujian/shared";
import { artifactRoot, ensureStorageDirs } from "./storage.js";

interface ExportPayload {
  project: Project;
  artifact: Artifact;
  chapters: ReportChapter[];
  facts: FactItem[];
  issues: QualityIssue[];
}

export async function generateArtifactFile(payload: ExportPayload) {
  await ensureStorageDirs();
  if (payload.artifact.format === "Word") return generateDocx(payload);
  if (payload.artifact.format === "Excel") return generateXlsx(payload);
  if (payload.artifact.format === "Archive") return generateArchive(payload);
  return generateText(payload);
}

async function generateDocx(payload: ExportPayload) {
  const doc = new Document({
    sections: [
      {
        children: [
          new Paragraph({ children: [new TextRun({ text: payload.project.name, bold: true, size: 32 })] }),
          new Paragraph(`成果：${payload.artifact.name}`),
          new Paragraph(`生成时间：${new Date().toLocaleString("zh-CN")}`),
          new Paragraph(""),
          ...payload.chapters.flatMap((chapter) => [
            new Paragraph({ children: [new TextRun({ text: `${chapter.no}. ${chapter.title}`, bold: true, size: 26 })] }),
            new Paragraph(`状态：${chapter.status}；引用数：${chapter.citationCount}`)
          ])
        ]
      }
    ]
  });
  const buffer = await Packer.toBuffer(doc);
  return writeBuffer(`${payload.artifact.name}.docx`, buffer, "application/vnd.openxmlformats-officedocument.wordprocessingml.document");
}

async function generateXlsx(payload: ExportPayload) {
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(payload.facts), "事实指标");
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(payload.issues), "质量问题");
  const buffer = XLSX.write(workbook, { type: "buffer", bookType: "xlsx" }) as Buffer;
  return writeBuffer(`${payload.artifact.name}.xlsx`, buffer, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
}

async function generateArchive(payload: ExportPayload) {
  const zip = new JSZip();
  zip.file("project.json", JSON.stringify(payload.project, null, 2));
  zip.file("facts.json", JSON.stringify(payload.facts, null, 2));
  zip.file("chapters.json", JSON.stringify(payload.chapters, null, 2));
  zip.file("quality-issues.json", JSON.stringify(payload.issues, null, 2));
  const buffer = await zip.generateAsync({ type: "nodebuffer" });
  return writeBuffer(`${payload.artifact.name}.zip`, buffer, "application/zip");
}

async function generateText(payload: ExportPayload) {
  return writeBuffer(`${payload.artifact.name}.txt`, Buffer.from(JSON.stringify(payload, null, 2), "utf8"), "text/plain; charset=utf-8");
}

async function writeBuffer(name: string, buffer: Buffer, mimeType: string) {
  const safeName = name.replace(/[\\/:*?"<>|]/g, "_");
  const storagePath = path.join(artifactRoot, `${Date.now()}-${safeName}`);
  await fs.writeFile(storagePath, buffer);
  return {
    storagePath,
    fileSize: buffer.length,
    mimeType
  };
}
