from __future__ import annotations

import time
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    AppUser,
    Artifact,
    AuditLog,
    ChapterCitation,
    DocumentChunk,
    FactItem,
    InvestmentEstimate,
    KnowledgeItem,
    ParseJob,
    Project,
    ProjectDocument,
    QualityCheckJob,
    QualityIssue,
    QualityRule,
    ReportChapter,
    ReportTemplate,
)
from app.db.session import get_db
from app.services.artifacts import generate_artifact
from app.services.auth import authenticate_user, get_session_user, logout_session
from app.services.capabilities import platform_status
from app.services.dashboard import build_dashboard
from app.services.documents import parse_document
from app.services.estimates import calculate_estimate, confirm_estimate, get_estimate, map_estimate
from app.services.jobs import enqueue_or_run
from app.services.model_gateway import gateway_status, generate_text
from app.services.quality import run_quality_check
from app.services.rag import generate_chapter_with_rag
from app.services.storage import persist_upload, storage
from app.worker.tasks import export_artifact_task, parse_document_task, quality_check_task

app = FastAPI(title="住建项目策划平台 API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    email: str
    password: str


class ProjectCreate(BaseModel):
    name: str
    type: str | None = None
    location: str | None = None
    owner: str | None = None


class DocumentCreate(BaseModel):
    name: str
    category: str | None = None
    version: str | None = None
    source: str | None = None


class FactUpdate(BaseModel):
    value: str | None = None
    unit: str | None = None
    source: str | None = None
    owner: str | None = None
    status: str | None = None


class ChapterUpdate(BaseModel):
    status: str | None = None
    content: str | None = None


class IssueUpdate(BaseModel):
    status: str


class ParseJobCreate(BaseModel):
    documentId: str | None = None


class QualityCheckCreate(BaseModel):
    projectId: str | None = None


class ModelGenerateRequest(BaseModel):
    prompt: str
    context: list[dict] = []


def bearer_token(authorization: Annotated[str | None, Header()] = None) -> str | None:
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ")
    return None


def current_user(db: Session = Depends(get_db), token: str | None = Depends(bearer_token)) -> dict:
    user = get_session_user(db, token)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    ok = db.scalar(select(text("1")))
    return {
        "ok": ok == 1,
        "service": settings.app_name,
        "phase": "phase-1-pdd-baseline",
        "database": "connected" if ok == 1 else "unknown",
        "schema": settings.pg_schema,
        "storage": "minio-configured" if settings.storage_mode != "local" else "local",
        "time": db.scalar(select(func.now())).isoformat(),
    }


@app.get("/api/platform/status")
def get_platform_status(db: Session = Depends(get_db)) -> dict:
    return platform_status(db)


@app.get("/api/model-gateway/status")
def get_model_gateway_status() -> dict:
    return gateway_status()


@app.post("/api/model-gateway/generate")
def model_gateway_generate(payload: ModelGenerateRequest, _: dict = Depends(current_user)) -> dict:
    return generate_text(payload.prompt, payload.context)


@app.get("/api/dashboard")
def dashboard(projectId: str | None = None, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    return build_dashboard(db, user, projectId)


@app.get("/api/bootstrap")
def bootstrap(db: Session = Depends(get_db)) -> dict:
    projects = db.scalars(select(Project).order_by(Project.created_at, Project.id)).all()
    return {
        "navGroups": nav_groups(),
        "workflow": workflow(),
        "routeMeta": route_meta(),
        "projects": [map_project(row) for row in projects],
        "documents": [map_document(db, row) for row in db.scalars(select(ProjectDocument).order_by(ProjectDocument.created_at, ProjectDocument.id)).all()],
        "facts": [map_fact(row) for row in db.scalars(select(FactItem).order_by(FactItem.id)).all()],
        "chapters": [map_chapter(row) for row in db.scalars(select(ReportChapter).order_by(ReportChapter.chapter_no)).all()],
        "qualityIssues": [map_issue(row) for row in db.scalars(select(QualityIssue).order_by(QualityIssue.id)).all()],
        "artifacts": [map_artifact(row) for row in db.scalars(select(Artifact).order_by(Artifact.id)).all()],
        "users": [map_user(row) for row in db.scalars(select(AppUser).order_by(AppUser.id)).all()],
        "templates": [map_template(row) for row in db.scalars(select(ReportTemplate).order_by(ReportTemplate.id)).all()],
        "knowledgeItems": [map_knowledge(row) for row in db.scalars(select(KnowledgeItem).order_by(KnowledgeItem.id)).all()],
        "auditLogs": [map_audit(row) for row in db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(20)).all()],
        "qualityRules": [map_rule(row) for row in db.scalars(select(QualityRule).order_by(QualityRule.id)).all()],
        "citations": [map_citation(row) for row in db.scalars(select(ChapterCitation).order_by(ChapterCitation.id)).all()],
        "documentChunks": [map_chunk(row) for row in db.scalars(select(DocumentChunk).order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)).all()],
    }


@app.post("/api/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    session = authenticate_user(db, payload.email, payload.password)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return session


@app.get("/api/auth/me")
def me(user: dict = Depends(current_user)) -> dict:
    return user


@app.post("/api/auth/logout")
def logout(db: Session = Depends(get_db), token: str | None = Depends(bearer_token), _: dict = Depends(current_user)) -> dict:
    logout_session(db, token)
    return {"ok": True}


@app.get("/api/projects")
def list_projects(db: Session = Depends(get_db)) -> list[dict]:
    return [map_project(row) for row in db.scalars(select(Project).order_by(Project.created_at, Project.id)).all()]


@app.post("/api/projects", status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    project = Project(
        id=f"P{int(time.time() * 1000)}",
        name=payload.name.strip(),
        type=payload.type or "可行性研究报告",
        location=payload.location or "待补充",
        phase="项目建档",
        owner=payload.owner or "项目负责人",
        progress=5,
        risk="一般",
    )
    db.add(project)
    write_audit(db, "system", "create_project", "project", project.id, payload.model_dump())
    db.commit()
    return map_project(project)


@app.get("/api/projects/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return map_project(project)


@app.get("/api/projects/{project_id}/documents")
def list_documents(project_id: str, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(ProjectDocument).where(ProjectDocument.project_id == project_id).order_by(ProjectDocument.created_at, ProjectDocument.id)).all()
    return [map_document(db, row) for row in rows]


@app.post("/api/projects/{project_id}/documents", status_code=201)
def create_document(project_id: str, payload: DocumentCreate, db: Session = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    document = ProjectDocument(
        id=f"D{int(time.time() * 1000)}",
        project_id=project_id,
        name=payload.name.strip(),
        category=payload.category or "待分类资料",
        version=payload.version or "v1.0",
        parse_status="待解析",
        source=payload.source or "人工登记",
        updated_at=current_day(db),
    )
    db.add(document)
    write_audit(db, "system", "create_document", "project_document", document.id, payload.model_dump())
    db.commit()
    return map_document(db, document)


@app.post("/api/projects/{project_id}/documents/upload", status_code=201)
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: dict = Depends(current_user),
) -> dict:
    key = f"documents/{int(time.time() * 1000)}-{file.filename}"
    storage_path, file_size, checksum = await persist_upload(file, key)
    document = ProjectDocument(
        id=f"D{int(time.time() * 1000)}",
        project_id=project_id,
        name=file.filename or "上传资料",
        category="上传资料",
        version="v1.0",
        parse_status="待解析",
        source="文件上传",
        updated_at=current_day(db),
        storage_path=storage_path,
        file_size=file_size,
        mime_type=file.content_type or "application/octet-stream",
        checksum=checksum,
    )
    db.add(document)
    write_audit(db, "system", "upload_document", "project_document", document.id, {"fileSize": file_size})
    db.commit()
    return map_document(db, document)


@app.get("/api/projects/{project_id}/facts")
def list_facts(project_id: str, db: Session = Depends(get_db)) -> list[dict]:
    return [map_fact(row) for row in db.scalars(select(FactItem).where(FactItem.project_id == project_id).order_by(FactItem.id)).all()]


@app.patch("/api/facts/{fact_id}")
def update_fact(fact_id: str, payload: FactUpdate, db: Session = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    fact = db.get(FactItem, fact_id)
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(fact, "fact_group" if key == "group" else key, value)
    write_audit(db, "system", "update_fact", "fact_item", fact_id, payload.model_dump(exclude_none=True))
    db.commit()
    return map_fact(fact)


@app.get("/api/projects/{project_id}/chapters")
def list_chapters(project_id: str, db: Session = Depends(get_db)) -> list[dict]:
    return [map_chapter(row) for row in db.scalars(select(ReportChapter).where(ReportChapter.project_id == project_id).order_by(ReportChapter.chapter_no)).all()]


@app.post("/api/chapters/{chapter_id}/generate", status_code=202)
def generate_chapter(chapter_id: str, db: Session = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    chapter = db.get(ReportChapter, chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    generated = generate_chapter_with_rag(db, chapter)
    facts = generated["facts"]
    chunks = generated["chunks"]
    content = generated["content"]
    chapter.content = content
    chapter.status = "编制中"
    chapter.citation_count = max(chapter.citation_count, len(facts))
    db.execute(delete(ChapterCitation).where(ChapterCitation.chapter_id == chapter_id))
    for fact in facts:
        linked = next((chunk for chunk in chunks if fact.name in chunk.content or fact.value in chunk.content), None)
        db.add(
            ChapterCitation(
                id=f"CIT-{chapter_id}-{fact.id}",
                chapter_id=chapter_id,
                fact_id=fact.id,
                document_id=linked.document_id if linked else None,
                chunk_id=linked.id if linked else None,
                excerpt=f"{fact.name}：{fact.value}{fact.unit or ''}",
                source=f"{fact.source}；{linked.locator}" if linked else fact.source,
            )
        )
    write_audit(db, "system", "generate_chapter_draft", "report_chapter", chapter_id, {"facts": len(facts), "chunks": len(chunks), "mode": generated["mode"]})
    db.commit()
    return {"chapter": map_chapter(chapter), "content": content, "mode": generated["mode"]}


@app.patch("/api/chapters/{chapter_id}")
def update_chapter(chapter_id: str, payload: ChapterUpdate, db: Session = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    chapter = db.get(ReportChapter, chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    if payload.status:
        chapter.status = payload.status
    if payload.content:
        chapter.content = payload.content
    write_audit(db, "system", "update_chapter", "report_chapter", chapter_id, payload.model_dump(exclude_none=True))
    db.commit()
    return map_chapter(chapter)


@app.get("/api/projects/{project_id}/quality-issues")
def list_quality_issues(project_id: str, db: Session = Depends(get_db)) -> list[dict]:
    return [map_issue(row) for row in db.scalars(select(QualityIssue).where(QualityIssue.project_id == project_id).order_by(QualityIssue.id)).all()]


@app.patch("/api/quality-issues/{issue_id}")
def update_quality_issue(issue_id: str, payload: IssueUpdate, db: Session = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    issue = db.get(QualityIssue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Quality issue not found")
    issue.status = payload.status
    write_audit(db, "system", "update_quality_issue", "quality_issue", issue_id, payload.model_dump())
    db.commit()
    return map_issue(issue)


@app.get("/api/projects/{project_id}/artifacts")
def list_artifacts(project_id: str, db: Session = Depends(get_db)) -> list[dict]:
    return [map_artifact(row) for row in db.scalars(select(Artifact).where(Artifact.project_id == project_id).order_by(Artifact.id)).all()]


@app.post("/api/artifacts/{artifact_id}/export", status_code=202)
def export_artifact(artifact_id: str, db: Session = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    artifact.status = "生成中"
    artifact.updated_at = current_day(db)
    write_audit(db, "system", "queue_artifact_export", "artifact", artifact_id, {"format": artifact.format})
    db.commit()
    result = enqueue_or_run(export_artifact_task, (artifact_id,), lambda: {"artifact": map_artifact(generate_artifact(db, artifact_id))})
    if result.get("execution") == "queued":
        return {**map_artifact(artifact), **result}
    refreshed = db.get(Artifact, artifact_id)
    return {**map_artifact(refreshed), **result}


@app.get("/api/artifacts/{artifact_id}/download")
def download_artifact(artifact_id: str, db: Session = Depends(get_db)) -> FileResponse:
    artifact = db.get(Artifact, artifact_id)
    if not artifact or artifact.status != "已生成" or not artifact.storage_path:
        raise HTTPException(status_code=404, detail="Generated artifact file not found")
    path = storage.download_to_temp(artifact.storage_path)
    return FileResponse(path, filename=artifact.name)


@app.post("/api/documents/parse-jobs", status_code=202)
def create_parse_job(payload: ParseJobCreate, db: Session = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    job = ParseJob(id=f"JOB-{int(time.time() * 1000)}", document_id=payload.documentId, status="queued", message="解析任务已进入后台处理。", result={})
    db.add(job)
    db.commit()
    return {"id": job.id, "documentId": job.document_id, "status": job.status, "message": job.message}


@app.post("/api/documents/{document_id}/parse", status_code=202)
def run_parse(document_id: str, db: Session = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    document = db.get(ProjectDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    job = ParseJob(id=f"JOB-{int(time.time() * 1000)}", document_id=document_id, status="queued", message="解析任务已进入后台处理。", result={})
    document.parse_status = "解析中"
    document.updated_at = current_day(db)
    db.add(job)
    write_audit(db, "system", "queue_document_parse", "project_document", document_id, {"jobId": job.id})
    db.commit()
    result = enqueue_or_run(parse_document_task, (document_id, job.id), lambda: parse_document(db, document_id, job.id) or {"status": "not_found"})
    if result.get("execution") == "queued":
        return {"job": {"id": job.id, "status": job.status}, "document": map_document(db, document), "chunks": 0, **result}
    refreshed = db.get(ProjectDocument, document_id)
    return {
        "job": result["job"],
        "document": map_document(db, refreshed),
        "chunks": result["chunks"],
        "execution": result.get("execution", "sync"),
        "queueError": result.get("queueError"),
    }


@app.post("/api/quality/checks", status_code=202)
def create_quality_check(payload: QualityCheckCreate, db: Session = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    if not payload.projectId:
        return run_quality_check(db, payload.projectId)
    result = enqueue_or_run(quality_check_task, (payload.projectId,), lambda: run_quality_check(db, payload.projectId))
    if result.get("execution") == "queued":
        return {"id": result["taskId"], "projectId": payload.projectId, "status": "queued", "message": "质量检查任务已进入后台处理。", **result}
    return result


@app.get("/api/templates")
def list_templates(db: Session = Depends(get_db)) -> list[dict]:
    return [map_template(row) for row in db.scalars(select(ReportTemplate).order_by(ReportTemplate.id)).all()]


@app.get("/api/knowledge")
def list_knowledge(db: Session = Depends(get_db)) -> list[dict]:
    return [map_knowledge(row) for row in db.scalars(select(KnowledgeItem).order_by(KnowledgeItem.id)).all()]


@app.get("/api/users")
def list_users(db: Session = Depends(get_db)) -> list[dict]:
    return [map_user(row) for row in db.scalars(select(AppUser).order_by(AppUser.id)).all()]


@app.get("/api/estimates/{project_id}")
def get_investment_estimate(project_id: str, db: Session = Depends(get_db)) -> dict:
    """Return the latest investment estimate for a project, or calculate one on the fly."""
    est = get_estimate(db, project_id)
    if est:
        return map_estimate(est)
    est = calculate_estimate(db, project_id)
    return map_estimate(est)


@app.post("/api/estimates/{project_id}/calculate", status_code=201)
def run_estimate_calculation(project_id: str, db: Session = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    """Force a fresh investment estimate calculation."""
    est = calculate_estimate(db, project_id)
    return map_estimate(est)


@app.post("/api/estimates/{estimate_id}/confirm")
def confirm_investment_estimate(estimate_id: str, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    """Confirm an investment estimate result."""
    try:
        est = confirm_estimate(db, estimate_id, user["name"])
        return map_estimate(est)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/audit-logs")
def list_audit_logs(db: Session = Depends(get_db)) -> list[dict]:
    return [map_audit(row) for row in db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(20)).all()]


def current_day(db: Session) -> str:
    return db.scalar(select(text("to_char(current_date, 'YYYY-MM-DD')")))


def write_audit(db: Session, actor: str, action: str, entity_type: str, entity_id: str, detail: dict) -> None:
    db.add(AuditLog(actor=actor, action=action, entity_type=entity_type, entity_id=entity_id, detail=detail))


def map_project(row: Project) -> dict:
    return {"id": row.id, "name": row.name, "type": row.type, "location": row.location, "phase": row.phase, "owner": row.owner, "progress": row.progress, "risk": row.risk}


def map_document(db: Session, row: ProjectDocument) -> dict:
    chunk_count = db.scalar(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.document_id == row.id)) or 0
    return {
        "id": row.id,
        "projectId": row.project_id,
        "name": row.name,
        "category": row.category,
        "version": row.version,
        "parseStatus": row.parse_status,
        "source": row.source,
        "updatedAt": row.updated_at,
        "storagePath": row.storage_path,
        "fileSize": row.file_size,
        "mimeType": row.mime_type,
        "checksum": row.checksum,
        "chunkCount": chunk_count,
    }


def map_fact(row: FactItem) -> dict:
    return {"id": row.id, "projectId": row.project_id, "group": row.fact_group, "name": row.name, "value": row.value, "unit": row.unit, "source": row.source, "owner": row.owner, "status": row.status}


def map_chapter(row: ReportChapter) -> dict:
    return {"id": row.id, "projectId": row.project_id, "no": row.chapter_no, "title": row.title, "owner": row.owner, "status": row.status, "citationCount": row.citation_count, "quality": row.quality}


def map_issue(row: QualityIssue) -> dict:
    return {"id": row.id, "projectId": row.project_id, "severity": row.severity, "type": row.type, "title": row.title, "owner": row.owner, "status": row.status}


def map_artifact(row: Artifact) -> dict:
    return {"id": row.id, "projectId": row.project_id, "name": row.name, "format": row.format, "status": row.status, "updatedAt": row.updated_at, "storagePath": row.storage_path, "fileSize": row.file_size, "generatedAt": row.generated_at.isoformat() if row.generated_at else None}


def map_user(row: AppUser) -> dict:
    return {"id": row.id, "name": row.name, "role": row.role, "department": row.department, "status": row.status, "email": row.email}


def map_template(row: ReportTemplate) -> dict:
    return {"id": row.id, "name": row.name, "reportType": row.report_type, "version": row.version, "status": row.status, "updatedAt": row.updated_at}


def map_knowledge(row: KnowledgeItem) -> dict:
    return {"id": row.id, "title": row.title, "category": row.category, "source": row.source, "status": row.status}


def map_audit(row: AuditLog) -> dict:
    return {"id": row.id, "actor": row.actor, "action": row.action, "entityType": row.entity_type, "entityId": row.entity_id, "createdAt": row.created_at.isoformat()}


def map_rule(row: QualityRule) -> dict:
    return {"id": row.id, "code": row.code, "name": row.name, "severity": row.severity, "target": row.target, "enabled": row.enabled, "description": row.description}


def map_citation(row: ChapterCitation) -> dict:
    return {"id": row.id, "chapterId": row.chapter_id, "factId": row.fact_id, "documentId": row.document_id, "chunkId": row.chunk_id, "excerpt": row.excerpt, "source": row.source}


def map_chunk(row: DocumentChunk) -> dict:
    return {"id": row.id, "projectId": row.project_id, "documentId": row.document_id, "chunkIndex": row.chunk_index, "content": row.content, "locator": row.locator}


def nav_groups() -> list[dict]:
    return [
        {"title": "项目作业", "items": [{"route": "dashboard", "label": "工作台", "count": "7"}, {"route": "projects", "label": "项目中心"}, {"route": "documents", "label": "资料中心", "count": "2"}, {"route": "facts", "label": "事实与指标", "count": "3"}, {"route": "report", "label": "编制工作台"}]},
        {"title": "分析与决策", "items": [{"route": "analysis", "label": "GIS与投资测算"}, {"route": "comparison", "label": "方案决策与收敛", "count": "后续"}, {"route": "quality", "label": "质量、审查与变更", "count": "5"}, {"route": "artifacts", "label": "成果中心"}]},
        {"title": "能力支撑", "items": [{"route": "knowledge", "label": "知识与模板"}, {"route": "system", "label": "系统管理"}]},
    ]


def workflow() -> list[dict]:
    return [
        {"no": 1, "name": "项目建档", "sub": "范围与权限", "route": "projects"},
        {"no": 2, "name": "资料清点", "sub": "版本与完整性", "route": "documents"},
        {"no": 3, "name": "事实确认", "sub": "统一数据底板", "route": "facts"},
        {"no": 4, "name": "章节编制", "sub": "初稿与引用", "route": "report"},
        {"no": 5, "name": "分析测算", "sub": "GIS与投资", "route": "analysis"},
        {"no": 6, "name": "专业复核", "sub": "会签与门禁", "route": "quality"},
        {"no": 7, "name": "成果输出", "sub": "发布与归档", "route": "artifacts"},
    ]


def route_meta() -> dict:
    return {
        "dashboard": ["工作台", "聚合跨项目任务、审核门禁、解析任务和风险提醒"],
        "projects": ["项目中心", "项目建档、项目成员、里程碑与项目级配置"],
        "documents": ["资料中心", "统一管理项目资料、版本、权限、解析状态和缺失清单"],
        "facts": ["事实与指标", "维护项目唯一可信事实底板、指标口径和变更影响"],
        "report": ["编制工作台", "按章节组织生成、编辑、引用、校核、审核和跨成果复用"],
        "analysis": ["GIS与投资测算", "开展可复现的区域分析、指标测算、投资估算和情景分析"],
        "comparison": ["方案决策与收敛", "第三阶段完善候选发散、筛选、评价、推荐和冻结闭环"],
        "quality": ["质量、审查与变更", "执行一致性检查、专业会签、决策门禁和发布控制"],
        "artifacts": ["成果中心", "生成报告、测算表、决策记录和项目归档包"],
        "knowledge": ["知识与模板", "管理政策、案例、规范摘要、报告模板和审查规则"],
        "system": ["系统管理", "维护组织权限、模型网关、数据源、安全和审计日志"],
    }
