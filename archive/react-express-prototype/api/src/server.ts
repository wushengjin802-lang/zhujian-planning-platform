import cors from "cors";
import express from "express";
import multer from "multer";
import { config } from "./config.js";
import { pool } from "./db/pool.js";
import {
  authenticateUser,
  createDocument,
  createParseJob,
  createProject,
  createUploadedDocument,
  generateChapterDraft,
  getAuditLogs,
  createQualityCheckJob,
  getArtifactFile,
  getArtifacts,
  getBootstrap,
  getChapters,
  getDocuments,
  getFacts,
  getKnowledgeItems,
  getProject,
  getProjects,
  getQualityIssues,
  getSessionUser,
  getTemplates,
  getUsers,
  logoutSession,
  requestArtifactExport,
  runDocumentParse,
  updateChapter,
  updateFact,
  updateQualityIssue
} from "./db/repository.js";
import { checksumFile, ensureStorageDirs, safeStoragePath, uploadRoot } from "./storage.js";

const app = express();
await ensureStorageDirs();
const upload = multer({ dest: uploadRoot });

app.use(cors());
app.use(express.json({ limit: "5mb" }));

const asyncHandler =
  (handler: express.RequestHandler): express.RequestHandler =>
  (req, res, next) => {
    Promise.resolve(handler(req, res, next)).catch(next);
  };

function routeParam(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value ?? "";
}

const factStatuses = new Set(["待确认", "已确认", "已锁定", "有冲突"]);
const chapterStatuses = new Set(["未开始", "编制中", "待审核", "已审核"]);
const issueStatuses = new Set(["待处理", "处理中", "已关闭"]);

function bearerToken(req: express.Request) {
  const header = req.headers.authorization;
  if (!header?.startsWith("Bearer ")) return undefined;
  return header.slice("Bearer ".length);
}

const authRequired: express.RequestHandler = async (req, res, next) => {
  try {
    const token = bearerToken(req);
    const user = token ? await getSessionUser(token) : undefined;
    if (!user) {
      res.status(401).json({ message: "Authentication required" });
      return;
    }
    next();
  } catch (error) {
    next(error);
  }
};

app.get(
  "/health",
  asyncHandler(async (_req, res) => {
    const db = await pool.query<{ ok: number }>("select 1 as ok");
    res.json({
      ok: true,
      service: "zhujian-planning-api",
      phase: "phase-1-mvp",
      database: db.rows[0]?.ok === 1 ? "connected" : "unknown",
      schema: config.pgSchema,
      time: new Date().toISOString()
    });
  })
);

app.get(
  "/api/bootstrap",
  asyncHandler(async (_req, res) => {
    res.json(await getBootstrap());
  })
);

app.post(
  "/api/auth/login",
  asyncHandler(async (req, res) => {
    const body = req.body as { email?: string; password?: string };
    if (!body.email || !body.password) {
      res.status(400).json({ message: "Email and password are required" });
      return;
    }
    const session = await authenticateUser(body.email, body.password);
    if (!session) {
      res.status(401).json({ message: "Invalid credentials" });
      return;
    }
    res.json(session);
  })
);

app.get(
  "/api/auth/me",
  asyncHandler(async (req, res) => {
    const token = bearerToken(req);
    const user = token ? await getSessionUser(token) : undefined;
    if (!user) {
      res.status(401).json({ message: "Authentication required" });
      return;
    }
    res.json(user);
  })
);

app.post(
  "/api/auth/logout",
  authRequired,
  asyncHandler(async (req, res) => {
    const token = bearerToken(req);
    if (token) await logoutSession(token);
    res.json({ ok: true });
  })
);

app.get(
  "/api/projects",
  asyncHandler(async (_req, res) => {
    res.json(await getProjects());
  })
);

app.post(
  "/api/projects",
  authRequired,
  asyncHandler(async (req, res) => {
    const body = req.body as { name?: string; type?: string; location?: string; owner?: string };
    if (!body.name?.trim()) {
      res.status(400).json({ message: "Project name is required" });
      return;
    }
    res.status(201).json(await createProject({ ...body, name: body.name.trim() }));
  })
);

app.get(
  "/api/projects/:id",
  asyncHandler(async (req, res) => {
    const project = await getProject(routeParam(req.params.id));
    if (!project) {
      res.status(404).json({ message: "Project not found" });
      return;
    }
    res.json(project);
  })
);

app.get(
  "/api/projects/:id/documents",
  asyncHandler(async (req, res) => {
    res.json(await getDocuments(routeParam(req.params.id)));
  })
);

app.post(
  "/api/projects/:id/documents",
  authRequired,
  asyncHandler(async (req, res) => {
    const projectId = routeParam(req.params.id);
    const body = req.body as { name?: string; category?: string; version?: string; source?: string };
    if (!body.name?.trim()) {
      res.status(400).json({ message: "Document name is required" });
      return;
    }
    res.status(201).json(await createDocument(projectId, { ...body, name: body.name.trim() }));
  })
);

app.post(
  "/api/projects/:id/documents/upload",
  authRequired,
  upload.single("file"),
  asyncHandler(async (req, res) => {
    const projectId = routeParam(req.params.id);
    if (!req.file) {
      res.status(400).json({ message: "Upload file is required" });
      return;
    }
    const checksum = await checksumFile(req.file.path);
    const document = await createUploadedDocument(projectId, {
      name: req.file.originalname,
      category: typeof req.body.category === "string" ? req.body.category : "上传资料",
      version: typeof req.body.version === "string" ? req.body.version : "v1.0",
      source: "文件上传",
      storagePath: req.file.path,
      fileSize: req.file.size,
      mimeType: req.file.mimetype || "application/octet-stream",
      checksum
    });
    res.status(201).json(document);
  })
);

app.get(
  "/api/projects/:id/facts",
  asyncHandler(async (req, res) => {
    res.json(await getFacts(routeParam(req.params.id)));
  })
);

app.patch(
  "/api/facts/:id",
  authRequired,
  asyncHandler(async (req, res) => {
    const body = req.body as Parameters<typeof updateFact>[1];
    if (body.status && !factStatuses.has(body.status)) {
      res.status(400).json({ message: "Invalid fact status" });
      return;
    }
    const fact = await updateFact(routeParam(req.params.id), body);
    if (!fact) {
      res.status(404).json({ message: "Fact not found" });
      return;
    }
    res.json(fact);
  })
);

app.get(
  "/api/projects/:id/chapters",
  asyncHandler(async (req, res) => {
    res.json(await getChapters(routeParam(req.params.id)));
  })
);

app.post(
  "/api/chapters/:id/generate",
  authRequired,
  asyncHandler(async (req, res) => {
    const result = await generateChapterDraft(routeParam(req.params.id));
    if (!result) {
      res.status(404).json({ message: "Chapter not found" });
      return;
    }
    res.status(202).json(result);
  })
);

app.patch(
  "/api/chapters/:id",
  authRequired,
  asyncHandler(async (req, res) => {
    const body = req.body as Parameters<typeof updateChapter>[1];
    if (body.status && !chapterStatuses.has(body.status)) {
      res.status(400).json({ message: "Invalid chapter status" });
      return;
    }
    const chapter = await updateChapter(routeParam(req.params.id), body);
    if (!chapter) {
      res.status(404).json({ message: "Chapter not found" });
      return;
    }
    res.json(chapter);
  })
);

app.get(
  "/api/projects/:id/quality-issues",
  asyncHandler(async (req, res) => {
    res.json(await getQualityIssues(routeParam(req.params.id)));
  })
);

app.patch(
  "/api/quality-issues/:id",
  authRequired,
  asyncHandler(async (req, res) => {
    const body = req.body as { status?: "待处理" | "处理中" | "已关闭" };
    if (!body.status || !issueStatuses.has(body.status)) {
      res.status(400).json({ message: "Valid issue status is required" });
      return;
    }
    const issue = await updateQualityIssue(routeParam(req.params.id), { status: body.status });
    if (!issue) {
      res.status(404).json({ message: "Quality issue not found" });
      return;
    }
    res.json(issue);
  })
);

app.get(
  "/api/projects/:id/artifacts",
  asyncHandler(async (req, res) => {
    res.json(await getArtifacts(routeParam(req.params.id)));
  })
);

app.post(
  "/api/artifacts/:id/export",
  authRequired,
  asyncHandler(async (req, res) => {
    const artifact = await requestArtifactExport(routeParam(req.params.id));
    if (!artifact) {
      res.status(404).json({ message: "Artifact not found" });
      return;
    }
    res.status(202).json(artifact);
  })
);

app.get(
  "/api/artifacts/:id/download",
  asyncHandler(async (req, res) => {
    const file = await getArtifactFile(routeParam(req.params.id));
    if (!file) {
      res.status(404).json({ message: "Generated artifact file not found" });
      return;
    }
    res.download(safeStoragePath(file.storage_path), file.name);
  })
);

app.post(
  "/api/documents/parse-jobs",
  authRequired,
  asyncHandler(async (req, res) => {
    const { documentId } = req.body as { documentId?: string };
    res.status(202).json(await createParseJob(documentId));
  })
);

app.post(
  "/api/documents/:id/parse",
  authRequired,
  asyncHandler(async (req, res) => {
    const result = await runDocumentParse(routeParam(req.params.id));
    if (!result) {
      res.status(404).json({ message: "Document not found" });
      return;
    }
    res.status(202).json(result);
  })
);

app.post(
  "/api/quality/checks",
  authRequired,
  asyncHandler(async (req, res) => {
    const { projectId } = req.body as { projectId?: string };
    res.status(202).json(await createQualityCheckJob(projectId));
  })
);

app.get(
  "/api/templates",
  asyncHandler(async (_req, res) => {
    res.json(await getTemplates());
  })
);

app.get(
  "/api/knowledge",
  asyncHandler(async (_req, res) => {
    res.json(await getKnowledgeItems());
  })
);

app.get(
  "/api/users",
  asyncHandler(async (_req, res) => {
    res.json(await getUsers());
  })
);

app.get(
  "/api/audit-logs",
  asyncHandler(async (_req, res) => {
    res.json(await getAuditLogs());
  })
);

app.use((error: unknown, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  console.error(error);
  res.status(500).json({
    message: "Internal server error",
    detail: error instanceof Error ? error.message : "Unknown error"
  });
});

app.listen(config.port, () => {
  console.log(`API listening on http://localhost:${config.port}`);
});
