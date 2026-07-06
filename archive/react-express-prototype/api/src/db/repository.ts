import {
  bootstrap,
  navGroups,
  routeMeta,
  workflow,
  type Artifact,
  type AppUser,
  type AuditLog,
  type BootstrapPayload,
  type ChapterCitation,
  type DocumentChunk,
  type FactItem,
  type KnowledgeItem,
  type Project,
  type ProjectDocument,
  type QualityIssue,
  type ReportChapter,
  type ReportTemplate,
  type QualityRule
} from "@zhujian/shared";
import type { QueryResultRow } from "pg";
import { pool } from "./pool.js";
import { createSessionToken, hashToken, verifyPassword } from "../auth.js";
import { chunkText, extractDocumentText } from "../documentParser.js";
import { generateArtifactFile } from "../exporters.js";

type QueryValue = string | number | null | undefined;

async function queryRows<T extends QueryResultRow>(sql: string, values: QueryValue[] = []) {
  const result = await pool.query<T>(sql, values);
  return result.rows;
}

export async function getProjects(): Promise<Project[]> {
  const rows = await queryRows<ProjectRow>("select id, name, type, location, phase, owner, progress, risk from projects order by created_at, id");
  return rows.map(mapProject);
}

export async function getProject(id: string): Promise<Project | undefined> {
  const rows = await queryRows<ProjectRow>("select id, name, type, location, phase, owner, progress, risk from projects where id = $1", [id]);
  return rows[0] ? mapProject(rows[0]) : undefined;
}

export async function getDocuments(projectId: string): Promise<ProjectDocument[]> {
  const rows = await queryRows<DocumentRow>(
    `select id, project_id, name, category, version, parse_status, source, updated_at,
            storage_path, file_size, mime_type, checksum,
            (select count(*)::int from document_chunks c where c.document_id = project_documents.id) as chunk_count
     from project_documents
     where project_id = $1
     order by created_at, id`,
    [projectId]
  );
  return rows.map(mapDocument);
}

export async function getFacts(projectId: string): Promise<FactItem[]> {
  const rows = await queryRows<FactRow>(
    "select id, project_id, fact_group, name, value, unit, source, owner, status from fact_items where project_id = $1 order by created_at, id",
    [projectId]
  );
  return rows.map(mapFact);
}

export async function getChapters(projectId: string): Promise<ReportChapter[]> {
  const rows = await queryRows<ChapterRow>(
    "select id, project_id, chapter_no, title, owner, status, citation_count, quality from report_chapters where project_id = $1 order by chapter_no",
    [projectId]
  );
  return rows.map(mapChapter);
}

export async function getQualityIssues(projectId: string): Promise<QualityIssue[]> {
  const rows = await queryRows<QualityIssueRow>(
    "select id, project_id, severity, type, title, owner, status from quality_issues where project_id = $1 order by created_at, id",
    [projectId]
  );
  return rows.map(mapQualityIssue);
}

export async function getArtifacts(projectId: string): Promise<Artifact[]> {
  const rows = await queryRows<ArtifactRow>(
    `select id, project_id, name, format, status, updated_at,
            storage_path, file_size, generated_at::text
     from artifacts
     where project_id = $1
     order by created_at, id`,
    [projectId]
  );
  return rows.map(mapArtifact);
}

export async function getDocumentChunks(projectId?: string): Promise<DocumentChunk[]> {
  const rows = await queryRows<DocumentChunkRow>(
    projectId
      ? "select id, project_id, document_id, chunk_index, content, locator from document_chunks where project_id = $1 order by document_id, chunk_index"
      : "select id, project_id, document_id, chunk_index, content, locator from document_chunks order by document_id, chunk_index",
    projectId ? [projectId] : []
  );
  return rows.map(mapDocumentChunk);
}

export async function getUsers(): Promise<AppUser[]> {
  const rows = await queryRows<UserRow>("select id, name, role, department, status, email from app_users order by created_at, id");
  return rows.map(mapUser);
}

export async function getQualityRules(): Promise<QualityRule[]> {
  const rows = await queryRows<QualityRuleRow>(
    "select id, code, name, severity, target, enabled, description from quality_rules order by created_at, id"
  );
  return rows.map(mapQualityRule);
}

export async function getCitations(): Promise<ChapterCitation[]> {
  const rows = await queryRows<CitationRow>(
    "select id, chapter_id, fact_id, document_id, chunk_id, excerpt, source from chapter_citations order by created_at, id"
  );
  return rows.map(mapCitation);
}

export async function getTemplates(): Promise<ReportTemplate[]> {
  const rows = await queryRows<TemplateRow>("select id, name, report_type, version, status, updated_at from report_templates order by created_at, id");
  return rows.map(mapTemplate);
}

export async function getKnowledgeItems(): Promise<KnowledgeItem[]> {
  const rows = await queryRows<KnowledgeRow>("select id, title, category, source, status from knowledge_items order by created_at, id");
  return rows.map(mapKnowledge);
}

export async function getAuditLogs(limit = 20): Promise<AuditLog[]> {
  const rows = await queryRows<AuditRow>(
    "select id::int, actor, action, entity_type, entity_id, created_at::text from audit_logs order by created_at desc limit $1",
    [limit]
  );
  return rows.map(mapAudit);
}

export async function getBootstrap(): Promise<BootstrapPayload> {
  const projects = await getProjects();
  if (projects.length === 0) {
    return bootstrap;
  }

  const [documents, facts, chapters, qualityIssues, artifacts] = await Promise.all([
    queryRows<DocumentRow>(
      `select id, project_id, name, category, version, parse_status, source, updated_at,
              storage_path, file_size, mime_type, checksum,
              (select count(*)::int from document_chunks c where c.document_id = project_documents.id) as chunk_count
       from project_documents
       order by created_at, id`
    ),
    queryRows<FactRow>("select id, project_id, fact_group, name, value, unit, source, owner, status from fact_items order by created_at, id"),
    queryRows<ChapterRow>("select id, project_id, chapter_no, title, owner, status, citation_count, quality from report_chapters order by chapter_no"),
    queryRows<QualityIssueRow>("select id, project_id, severity, type, title, owner, status from quality_issues order by created_at, id"),
    queryRows<ArtifactRow>(
      `select id, project_id, name, format, status, updated_at,
              storage_path, file_size, generated_at::text
       from artifacts
       order by created_at, id`
    )
  ]);
  const [users, templates, knowledgeItems, auditLogs, qualityRules, citations, documentChunks] = await Promise.all([
    getUsers(),
    getTemplates(),
    getKnowledgeItems(),
    getAuditLogs(),
    getQualityRules(),
    getCitations(),
    getDocumentChunks()
  ]);

  return {
    navGroups,
    workflow,
    routeMeta,
    projects,
    documents: documents.map(mapDocument),
    facts: facts.map(mapFact),
    chapters: chapters.map(mapChapter),
    qualityIssues: qualityIssues.map(mapQualityIssue),
    artifacts: artifacts.map(mapArtifact),
    users,
    templates,
    knowledgeItems,
    auditLogs,
    qualityRules,
    citations,
    documentChunks
  };
}

export async function authenticateUser(email: string, password: string) {
  const rows = await queryRows<AuthUserRow>(
    "select id, name, role, department, status, email, password_hash, password_salt from app_users where email = $1 and status = '启用'",
    [email]
  );
  const user = rows[0];
  if (!user?.password_hash || !user.password_salt || !verifyPassword(password, user.password_salt, user.password_hash)) {
    return undefined;
  }
  const token = createSessionToken();
  const tokenHash = hashToken(token);
  await pool.query(
    "insert into auth_sessions (token_hash, user_id, expires_at) values ($1, $2, now() + interval '8 hours')",
    [tokenHash, user.id]
  );
  await writeAudit(user.name, "login", "auth_session", user.id, { email });
  return { token, user: mapUser(user) };
}

export async function getSessionUser(token: string): Promise<AppUser | undefined> {
  const rows = await queryRows<UserRow>(
    `select u.id, u.name, u.role, u.department, u.status, u.email
     from auth_sessions s
     join app_users u on u.id = s.user_id
     where s.token_hash = $1 and s.expires_at > now() and u.status = '启用'`,
    [hashToken(token)]
  );
  return rows[0] ? mapUser(rows[0]) : undefined;
}

export async function logoutSession(token: string) {
  await pool.query("delete from auth_sessions where token_hash = $1", [hashToken(token)]);
}

export async function createProject(input: {
  name: string;
  type?: string;
  location?: string;
  owner?: string;
}) {
  const id = `P${Date.now()}`;
  const rows = await queryRows<ProjectRow>(
    `insert into projects (id, name, type, location, phase, owner, progress, risk)
     values ($1, $2, $3, $4, $5, $6, $7, $8)
     returning id, name, type, location, phase, owner, progress, risk`,
    [
      id,
      input.name,
      input.type ?? "可行性研究报告",
      input.location ?? "待补充",
      "项目建档",
      input.owner ?? "项目负责人",
      5,
      "一般"
    ]
  );
  await writeAudit("system", "create_project", "project", id, input);
  return mapProject(rows[0]);
}

export async function createDocument(projectId: string, input: {
  name: string;
  category?: string;
  version?: string;
  source?: string;
}) {
  const id = `D${Date.now()}`;
  const rows = await queryRows<DocumentRow>(
    `insert into project_documents (id, project_id, name, category, version, parse_status, source, updated_at)
     values ($1, $2, $3, $4, $5, $6, $7, to_char(current_date, 'YYYY-MM-DD'))
     returning id, project_id, name, category, version, parse_status, source, updated_at`,
    [
      id,
      projectId,
      input.name,
      input.category ?? "待分类资料",
      input.version ?? "v1.0",
      "待解析",
      input.source ?? "人工登记"
    ]
  );
  await writeAudit("system", "create_document", "project_document", id, { projectId, ...input });
  return mapDocument(rows[0]);
}

export async function createUploadedDocument(projectId: string, input: {
  name: string;
  category?: string;
  version?: string;
  source?: string;
  storagePath: string;
  fileSize: number;
  mimeType: string;
  checksum: string;
}) {
  const id = `D${Date.now()}`;
  const rows = await queryRows<DocumentRow>(
    `insert into project_documents
       (id, project_id, name, category, version, parse_status, source, updated_at, storage_path, file_size, mime_type, checksum)
     values ($1, $2, $3, $4, $5, $6, $7, to_char(current_date, 'YYYY-MM-DD'), $8, $9, $10, $11)
     returning id, project_id, name, category, version, parse_status, source, updated_at, storage_path, file_size, mime_type, checksum`,
    [
      id,
      projectId,
      input.name,
      input.category ?? "上传资料",
      input.version ?? "v1.0",
      "待解析",
      input.source ?? "文件上传",
      input.storagePath,
      input.fileSize,
      input.mimeType,
      input.checksum
    ]
  );
  await writeAudit("system", "upload_document", "project_document", id, {
    projectId,
    name: input.name,
    fileSize: input.fileSize,
    checksum: input.checksum
  });
  return mapDocument(rows[0]);
}

export async function updateFact(id: string, input: {
  value?: string;
  unit?: string | null;
  source?: string;
  owner?: string;
  status?: FactItem["status"];
}) {
  const rows = await queryRows<FactRow>(
    `update fact_items
     set value = coalesce($2, value),
         unit = coalesce($3, unit),
         source = coalesce($4, source),
         owner = coalesce($5, owner),
         status = coalesce($6, status),
         updated_at = now()
     where id = $1
     returning id, project_id, fact_group, name, value, unit, source, owner, status`,
    [id, input.value, input.unit ?? undefined, input.source, input.owner, input.status]
  );
  if (!rows[0]) return undefined;
  await writeAudit("system", "update_fact", "fact_item", id, input);
  return mapFact(rows[0]);
}

export async function updateChapter(id: string, input: {
  status?: ReportChapter["status"];
  content?: string;
}) {
  const rows = await queryRows<ChapterRow>(
    `update report_chapters
     set status = coalesce($2, status),
         content = coalesce($3, content),
         updated_at = now()
     where id = $1
     returning id, project_id, chapter_no, title, owner, status, citation_count, quality`,
    [id, input.status, input.content]
  );
  if (!rows[0]) return undefined;
  await writeAudit("system", "update_chapter", "report_chapter", id, input);
  return mapChapter(rows[0]);
}

export async function generateChapterDraft(id: string) {
  const chapterRows = await queryRows<ChapterRow>(
    "select id, project_id, chapter_no, title, owner, status, citation_count, quality from report_chapters where id = $1",
    [id]
  );
  const chapter = chapterRows[0];
  if (!chapter) return undefined;
  const factRows = await queryRows<FactRow>(
    "select id, project_id, fact_group, name, value, unit, source, owner, status from fact_items where project_id = $1 and status in ('已确认', '已锁定') order by created_at limit 6",
    [chapter.project_id]
  );
  const chunkRows = await queryRows<DocumentChunkRow>(
    "select id, project_id, document_id, chunk_index, content, locator from document_chunks where project_id = $1 order by created_at, chunk_index limit 12",
    [chapter.project_id]
  );
  const content = [
    `# ${chapter.chapter_no}. ${chapter.title}`,
    "",
    "本章节由第一阶段 MVP 根据已确认事实、模板结构和知识库条目生成初稿，需专业人员复核。",
    "",
    ...factRows.map((fact) => `- ${fact.name}：${fact.value}${fact.unit ?? ""}（来源：${fact.source}）`)
  ].join("\n");
  const rows = await queryRows<ChapterRow>(
    `update report_chapters
     set content = $2,
         status = '编制中',
         citation_count = greatest(citation_count, $3),
         updated_at = now()
     where id = $1
     returning id, project_id, chapter_no, title, owner, status, citation_count, quality`,
    [id, content, factRows.length]
  );
  await pool.query("delete from chapter_citations where chapter_id = $1", [id]);
  for (const fact of factRows) {
    const linkedChunk = chunkRows.find((chunk) => chunk.content.includes(fact.name) || chunk.content.includes(fact.value));
    await pool.query(
      `insert into chapter_citations (id, chapter_id, fact_id, document_id, chunk_id, excerpt, source)
       values ($1, $2, $3, $4, $5, $6, $7)`,
      [
        `CIT-${id}-${fact.id}`,
        id,
        fact.id,
        linkedChunk?.document_id ?? null,
        linkedChunk?.id ?? null,
        `${fact.name}：${fact.value}${fact.unit ?? ""}`,
        linkedChunk ? `${fact.source}；${linkedChunk.locator}` : fact.source
      ]
    );
  }
  await writeAudit("system", "generate_chapter_draft", "report_chapter", id, { facts: factRows.length });
  return { chapter: mapChapter(rows[0]), content };
}

export async function updateQualityIssue(id: string, input: { status: QualityIssue["status"] }) {
  const rows = await queryRows<QualityIssueRow>(
    `update quality_issues
     set status = $2,
         updated_at = now()
     where id = $1
     returning id, project_id, severity, type, title, owner, status`,
    [id, input.status]
  );
  if (!rows[0]) return undefined;
  await writeAudit("system", "update_quality_issue", "quality_issue", id, input);
  return mapQualityIssue(rows[0]);
}

export async function requestArtifactExport(id: string) {
  const artifactRows = await queryRows<ArtifactRow>(
    "select id, project_id, name, format, status, updated_at, storage_path, file_size, generated_at::text from artifacts where id = $1",
    [id]
  );
  const artifact = artifactRows[0];
  if (!artifact) return undefined;

  const blockers = await queryRows<{ count: string }>(
    "select count(*)::text from quality_issues where project_id = $1 and severity = '阻断' and status <> '已关闭'",
    [artifact.project_id]
  );
  if (Number(blockers[0]?.count ?? 0) > 0) {
    const blockedRows = await queryRows<ArtifactRow>(
      `update artifacts
       set status = '受阻',
           updated_at = to_char(current_date, 'YYYY-MM-DD')
       where id = $1
       returning id, project_id, name, format, status, updated_at, storage_path, file_size, generated_at::text`,
      [id]
    );
    await writeAudit("system", "request_artifact_export_blocked", "artifact", id, { status: "受阻" });
    return mapArtifact(blockedRows[0]);
  }

  const [project, chapters, facts, issues] = await Promise.all([
    getProject(artifact.project_id),
    getChapters(artifact.project_id),
    getFacts(artifact.project_id),
    getQualityIssues(artifact.project_id)
  ]);
  if (!project) return undefined;
  const file = await generateArtifactFile({
    project,
    artifact: mapArtifact(artifact),
    chapters,
    facts,
    issues
  });
  const rows = await queryRows<ArtifactRow>(
    `update artifacts
     set status = '已生成',
         storage_path = $2,
         file_size = $3,
         generated_at = now(),
         updated_at = to_char(current_date, 'YYYY-MM-DD')
     where id = $1
     returning id, project_id, name, format, status, updated_at, storage_path, file_size, generated_at::text`,
    [id, file.storagePath, file.fileSize]
  );
  await writeAudit("system", "request_artifact_export", "artifact", id, { status: "已生成", storagePath: file.storagePath });
  return mapArtifact(rows[0]);
}

export async function runDocumentParse(documentId: string) {
  const id = `JOB-${Date.now()}`;
  const documentRows = await queryRows<DocumentRow>(
    "select id, project_id, name, category, version, parse_status, source, updated_at, storage_path, file_size, mime_type, checksum, 0::int as chunk_count from project_documents where id = $1",
    [documentId]
  );
  const document = documentRows[0];
  if (!document) return undefined;

  const text = document.storage_path ? await extractDocumentText(document.storage_path, document.mime_type ?? undefined) : "人工登记资料，无上传文件正文。";
  const chunks = chunkText(text);
  const result = {
    extractedChunks: chunks.length,
    suggestedCategory: document.category,
    completedAt: new Date().toISOString()
  };

  const client = await pool.connect();
  try {
    await client.query("begin");
    await client.query(
      `insert into parse_jobs (id, document_id, status, message, result)
       values ($1, $2, $3, $4, $5)`,
      [id, documentId, "completed", "资料解析已完成，抽取结果待人工确认。", JSON.stringify(result)]
    );
    await client.query("delete from document_chunks where document_id = $1", [documentId]);
    for (const [index, content] of chunks.entries()) {
      await client.query(
        `insert into document_chunks (id, project_id, document_id, chunk_index, content, locator)
         values ($1, $2, $3, $4, $5, $6)`,
        [`CHK-${documentId}-${index + 1}`, document.project_id, documentId, index + 1, content, `切片 ${index + 1}`]
      );
    }
    const rows = await client.query<DocumentRow>(
      `update project_documents
       set parse_status = '已解析',
           updated_at = to_char(current_date, 'YYYY-MM-DD')
       where id = $1
       returning id, project_id, name, category, version, parse_status, source, updated_at, storage_path, file_size, mime_type, checksum,
                 (select count(*)::int from document_chunks c where c.document_id = project_documents.id) as chunk_count`,
      [documentId]
    );
    await client.query(
      "insert into audit_logs (actor, action, entity_type, entity_id, detail) values ($1, $2, $3, $4, $5)",
      ["system", "run_document_parse", "project_document", documentId, JSON.stringify(result)]
    );
    await client.query("commit");
    return rows.rows[0] ? { job: { id, status: "completed", result }, document: mapDocument(rows.rows[0]), chunks: chunks.length } : undefined;
  } catch (error) {
    await client.query("rollback");
    throw error;
  } finally {
    client.release();
  }
}

export async function getArtifactFile(id: string) {
  const rows = await queryRows<GeneratedArtifactRow>(
    `select id, name, storage_path, file_size,
            case
              when format = 'Word' then 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
              when format = 'Excel' then 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
              when format = 'Archive' then 'application/zip'
              else 'application/octet-stream'
            end as mime_type
     from artifacts
     where id = $1 and status = '已生成' and storage_path is not null`,
    [id]
  );
  return rows[0];
}

export async function createParseJob(documentId?: string) {
  const id = `JOB-${Date.now()}`;
  const message = "解析任务已进入队列，后续将接入异步任务服务。";
  await pool.query(
    "insert into parse_jobs (id, document_id, status, message) values ($1, $2, $3, $4)",
    [id, documentId ?? null, "queued", message]
  );
  await writeAudit("system", "create_parse_job", "parse_job", id, { documentId });
  return { id, documentId, status: "queued", message };
}

export async function createQualityCheckJob(projectId?: string) {
  const id = `QC-${Date.now()}`;
  const message = "质量检查已完成，结果已写入质量问题表。";
  const rules = await getQualityRules();
  const enabledCodes = new Set(rules.filter((rule) => rule.enabled).map((rule) => rule.code));
  const factsConflict = projectId && enabledCodes.has("FACT_CONFLICT")
    ? await queryRows<{ count: string }>("select count(*)::text from fact_items where project_id = $1 and status = '有冲突'", [projectId])
    : [{ count: "0" }];
  const lowCitations = projectId && enabledCodes.has("LOW_CITATION")
    ? await queryRows<{ count: string }>("select count(*)::text from report_chapters where project_id = $1 and citation_count < 3", [projectId])
    : [{ count: "0" }];

  await pool.query(
    "insert into quality_check_jobs (id, project_id, status, message) values ($1, $2, $3, $4)",
    [id, projectId ?? null, "completed", message]
  );
  if (projectId && Number(factsConflict[0]?.count ?? 0) > 0) {
    await pool.query(
      `insert into quality_issues (id, project_id, severity, type, title, owner, status)
       values ($1, $2, '严重', '事实冲突', '质量检查发现仍存在未处理事实冲突', '系统', '待处理')
       on conflict (id) do nothing`,
      [`Q${Date.now()}F`, projectId]
    );
  }
  if (projectId && Number(lowCitations[0]?.count ?? 0) > 0) {
    await pool.query(
      `insert into quality_issues (id, project_id, severity, type, title, owner, status)
       values ($1, $2, '一般', '引用不足', '部分章节引用数量不足，需补充依据', '系统', '待处理')
       on conflict (id) do nothing`,
      [`Q${Date.now()}C`, projectId]
    );
  }
  await writeAudit("system", "create_quality_check_job", "quality_check_job", id, { projectId });
  return { id, projectId, status: "completed", message };
}

async function writeAudit(actor: string, action: string, entityType: string, entityId: string, detail: object) {
  await pool.query(
    "insert into audit_logs (actor, action, entity_type, entity_id, detail) values ($1, $2, $3, $4, $5)",
    [actor, action, entityType, entityId, JSON.stringify(detail)]
  );
}

interface ProjectRow {
  id: string;
  name: string;
  type: string;
  location: string;
  phase: string;
  owner: string;
  progress: number;
  risk: Project["risk"];
}

interface DocumentRow {
  id: string;
  project_id: string;
  name: string;
  category: string;
  version: string;
  parse_status: ProjectDocument["parseStatus"];
  source: string;
  updated_at: string;
  storage_path?: string | null;
  file_size?: number | string | null;
  mime_type?: string | null;
  checksum?: string | null;
  chunk_count?: number | null;
}

interface FactRow {
  id: string;
  project_id: string;
  fact_group: string;
  name: string;
  value: string;
  unit: string | null;
  source: string;
  owner: string;
  status: FactItem["status"];
}

interface ChapterRow {
  id: string;
  project_id: string;
  chapter_no: string;
  title: string;
  owner: string;
  status: ReportChapter["status"];
  citation_count: number;
  quality: ReportChapter["quality"];
}

interface QualityIssueRow {
  id: string;
  project_id: string;
  severity: QualityIssue["severity"];
  type: string;
  title: string;
  owner: string;
  status: QualityIssue["status"];
}

interface ArtifactRow {
  id: string;
  project_id: string;
  name: string;
  format: Artifact["format"];
  status: Artifact["status"];
  updated_at: string;
  storage_path?: string | null;
  file_size?: number | string | null;
  generated_at?: string | null;
}

interface UserRow {
  id: string;
  name: string;
  role: string;
  department: string;
  status: AppUser["status"];
  email: string | null;
}

interface AuthUserRow extends UserRow {
  password_hash: string | null;
  password_salt: string | null;
}

interface TemplateRow {
  id: string;
  name: string;
  report_type: string;
  version: string;
  status: ReportTemplate["status"];
  updated_at: string;
}

interface KnowledgeRow {
  id: string;
  title: string;
  category: string;
  source: string;
  status: KnowledgeItem["status"];
}

interface AuditRow {
  id: number;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  created_at: string;
}

interface QualityRuleRow {
  id: string;
  code: string;
  name: string;
  severity: QualityRule["severity"];
  target: QualityRule["target"];
  enabled: boolean;
  description: string;
}

interface CitationRow {
  id: string;
  chapter_id: string;
  fact_id: string | null;
  document_id: string | null;
  chunk_id: string | null;
  excerpt: string;
  source: string;
}

interface DocumentChunkRow {
  id: string;
  project_id: string;
  document_id: string;
  chunk_index: number;
  content: string;
  locator: string;
}

interface GeneratedArtifactRow {
  id: string;
  name: string;
  storage_path: string;
  file_size: number;
  mime_type: string;
}

function mapProject(row: ProjectRow): Project {
  return row;
}

function mapDocument(row: DocumentRow): ProjectDocument {
  return {
    id: row.id,
    projectId: row.project_id,
    name: row.name,
    category: row.category,
    version: row.version,
    parseStatus: row.parse_status,
    source: row.source,
    updatedAt: row.updated_at,
    storagePath: row.storage_path ?? undefined,
    fileSize: row.file_size == null ? undefined : Number(row.file_size),
    mimeType: row.mime_type ?? undefined,
    checksum: row.checksum ?? undefined,
    chunkCount: row.chunk_count ?? undefined
  };
}

function mapFact(row: FactRow): FactItem {
  return {
    id: row.id,
    projectId: row.project_id,
    group: row.fact_group,
    name: row.name,
    value: row.value,
    unit: row.unit ?? undefined,
    source: row.source,
    owner: row.owner,
    status: row.status
  };
}

function mapChapter(row: ChapterRow): ReportChapter {
  return {
    id: row.id,
    projectId: row.project_id,
    no: row.chapter_no,
    title: row.title,
    owner: row.owner,
    status: row.status,
    citationCount: row.citation_count,
    quality: row.quality
  };
}

function mapQualityIssue(row: QualityIssueRow): QualityIssue {
  return {
    id: row.id,
    projectId: row.project_id,
    severity: row.severity,
    type: row.type,
    title: row.title,
    owner: row.owner,
    status: row.status
  };
}

function mapArtifact(row: ArtifactRow): Artifact {
  return {
    id: row.id,
    projectId: row.project_id,
    name: row.name,
    format: row.format,
    status: row.status,
    updatedAt: row.updated_at,
    storagePath: row.storage_path ?? undefined,
    fileSize: row.file_size == null ? undefined : Number(row.file_size),
    generatedAt: row.generated_at ?? undefined
  };
}

function mapUser(row: UserRow): AppUser {
  return {
    id: row.id,
    name: row.name,
    role: row.role,
    department: row.department,
    status: row.status,
    email: row.email ?? undefined
  };
}

function mapTemplate(row: TemplateRow): ReportTemplate {
  return {
    id: row.id,
    name: row.name,
    reportType: row.report_type,
    version: row.version,
    status: row.status,
    updatedAt: row.updated_at
  };
}

function mapKnowledge(row: KnowledgeRow): KnowledgeItem {
  return row;
}

function mapAudit(row: AuditRow): AuditLog {
  return {
    id: row.id,
    actor: row.actor,
    action: row.action,
    entityType: row.entity_type,
    entityId: row.entity_id ?? undefined,
    createdAt: row.created_at
  };
}

function mapQualityRule(row: QualityRuleRow): QualityRule {
  return row;
}

function mapCitation(row: CitationRow): ChapterCitation {
  return {
    id: row.id,
    chapterId: row.chapter_id,
    factId: row.fact_id ?? undefined,
    documentId: row.document_id ?? undefined,
    chunkId: row.chunk_id ?? undefined,
    excerpt: row.excerpt,
    source: row.source
  };
}

function mapDocumentChunk(row: DocumentChunkRow): DocumentChunk {
  return {
    id: row.id,
    projectId: row.project_id,
    documentId: row.document_id,
    chunkIndex: row.chunk_index,
    content: row.content,
    locator: row.locator
  };
}
