from __future__ import annotations

import time
from datetime import datetime, timezone
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
    ProjectInitializationRecord,
    ProjectRegionRule,
    ProjectRuleMigrationPlan,
    ProjectRevision,
    ProjectWizardDraft,
    ProjectMaterialRequirement,
    ProjectMilestone,
    QualityCheckJob,
    QualityIssue,
    QualityRule,
    ReportChapter,
    ReportTemplate,
    Notification,
    NotificationSubscription,
    ProjectMember,
    ReviewTask,
    TaskEvent,
    WorkbenchEvent,
    WorkItem,
)
from app.db.session import get_db
from app.services.artifacts import generate_artifact
from app.services.auth import authenticate_user, get_session_user, logout_session
from app.services.capabilities import platform_status
from app.services.dashboard import build_dashboard
from app.services.project_center import add_default_milestones, apply_project_defaults, apply_rule_migration_plan, build_project_center, can_change_status, close_project_revision, create_project_revision, create_rule_migration_plan, ensure_project_initialization_package, ensure_project_member, evaluate_project_status_gate, generate_project_code, list_project_drafts, list_region_rules, map_milestone, map_material_requirement, map_project_draft, map_project_profile, map_project_revision, map_project_summary, map_region_rule, map_rule_migration_plan, preview_project_rule_migration, upsert_project_draft
from app.services.workbench import add_task_event, add_workbench_event, assert_project_visible, assert_review_approval_gate, is_management_role, map_task_event, map_workbench_event
from app.services.documents import parse_document
from app.services.estimates import calculate_estimate, confirm_estimate, get_estimate, map_estimate
from app.services.jobs import enqueue_or_run, revoke_task
from app.services.model_gateway import gateway_status, generate_text
from app.services.quality import run_quality_check
from app.services.rag import generate_chapter_with_rag
from app.services.storage import persist_upload, storage
from app.worker.tasks import export_artifact_task, parse_document_task, quality_check_task

app = FastAPI(title="住建项目策划平台 API", version="2.3.0")
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
    code: str | None = None
    templateId: str | None = None
    templateVersion: str | None = None
    region: str | None = None
    regionRuleId: str | None = None
    draftId: str | None = None
    confidentiality: str | None = None
    plannedStart: str | None = None
    plannedEnd: str | None = None
    description: str | None = None
    members: list[dict] = []
    milestones: list[dict] = []


class ProjectUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    location: str | None = None
    owner: str | None = None
    phase: str | None = None
    progress: int | None = None
    risk: str | None = None
    templateId: str | None = None
    templateVersion: str | None = None
    region: str | None = None
    regionRuleId: str | None = None
    draftId: str | None = None
    confidentiality: str | None = None
    plannedStart: str | None = None
    plannedEnd: str | None = None
    description: str | None = None


class ProjectMemberInput(BaseModel):
    userId: str
    role: str = "项目成员"


class ProjectMilestoneInput(BaseModel):
    name: str
    owner: str = "项目负责人"
    status: str = "未开始"
    dueAt: str | None = None
    sortOrder: int | None = None


class ProjectMaterialInput(BaseModel):
    status: str
    sourceType: str | None = None
    sourceId: str | None = None


class ProjectStatusAction(BaseModel):
    status: str
    reason: str | None = None


class ProjectCopyAction(BaseModel):
    name: str | None = None
    copyMembers: bool = True
    copyMilestones: bool = True
    copySettings: bool = True




class ProjectDraftInput(BaseModel):
    id: str | None = None
    name: str | None = None
    step: int = 0
    payload: dict = {}


class ProjectRegionRuleInput(BaseModel):
    id: str | None = None
    name: str
    region: str = "全国"
    projectType: str | None = None
    version: str = "v1.0"
    status: str = "已发布"
    description: str | None = None
    materials: list[dict] = []
    facts: list[dict] = []
    chapters: list[dict] = []
    artifacts: list[dict] = []
    settings: dict = {}


class ProjectMigrationPlanInput(BaseModel):
    templateId: str | None = None
    templateVersion: str | None = None
    regionRuleId: str | None = None


class ProjectRevisionInput(BaseModel):
    title: str | None = None
    reason: str | None = None


class ProjectRevisionCloseInput(BaseModel):
    status: str = "已确认"


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


class WorkItemAction(BaseModel):
    assigneeId: str | None = None
    comment: str | None = None


class ReviewAction(BaseModel):
    comment: str | None = None
    reviewerId: str | None = None


class CommentAction(BaseModel):
    comment: str


class NotificationBatchAction(BaseModel):
    projectId: str | None = None


class TaskAction(BaseModel):
    taskKind: str
    force: bool = False


class NotificationSubscriptionUpdate(BaseModel):
    enabled: bool = True
    delivery: str = "in_app"



def bearer_token(authorization: Annotated[str | None, Header()] = None) -> str | None:
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ")
    return None


def current_user(db: Session = Depends(get_db), token: str | None = Depends(bearer_token)) -> dict:
    user = get_session_user(db, token)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _is_same_user(value: str | None, user: dict) -> bool:
    return bool(value and value == user.get("id"))


def _can_manage_workbench(user: dict) -> bool:
    return is_management_role(user.get("role"))


def _notification_event_label(event_type: str) -> str:
    labels = {
        "work_item_sla": "工作项SLA提醒",
        "review_task_sla": "审核任务SLA提醒",
        "quality_issue": "质量问题提醒",
        "task_stuck": "任务卡住提醒",
        "review_assignment": "审核分配提醒",
    }
    return labels.get(event_type, event_type)


def map_subscription(row: NotificationSubscription) -> dict:
    return {
        "eventType": row.event_type,
        "label": _notification_event_label(row.event_type),
        "enabled": row.enabled,
        "delivery": row.delivery,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def _default_subscriptions(user: dict) -> list[dict]:
    return [
        {"eventType": item, "label": _notification_event_label(item), "enabled": True, "delivery": "in_app", "updatedAt": None}
        for item in ["work_item_sla", "review_task_sla", "quality_issue", "task_stuck", "review_assignment"]
    ]


def assert_work_item_actor(item: WorkItem, user: dict, action: str) -> None:
    """Limit state-changing work-item actions to the assignee or management roles.

    Claiming an unassigned item remains open to visible project members, but completing,
    cancelling or transferring another person's item is blocked. This keeps the
    workbench inside its intended coordination boundary without introducing a full RBAC layer.
    """
    if _can_manage_workbench(user):
        return
    if action == "claim" and not item.assignee_id:
        return
    if _is_same_user(item.assignee_id, user):
        return
    raise HTTPException(status_code=403, detail="仅工作项负责人或管理角色可执行该操作")


def assert_review_task_actor(task: ReviewTask, user: dict, action: str) -> None:
    """Limit review decisions to assigned reviewers or management roles.

    Comments and countersign are still allowed for visible project members, because they
    are collaboration records rather than final review decisions.
    """
    if action in {"comment", "countersign"}:
        return
    if _can_manage_workbench(user) or _is_same_user(task.reviewer_id, user):
        return
    if action == "assign" and not task.reviewer_id:
        return
    raise HTTPException(status_code=403, detail="仅指定审核人或管理角色可执行该审核操作")


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




@app.get("/api/work-items/{item_id}/events")
def list_work_item_events(item_id: str, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> list[dict]:
    item = db.get(WorkItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")
    try:
        assert_project_visible(db, user, item.project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    rows = db.scalars(select(WorkbenchEvent).where(WorkbenchEvent.target_type == "work_item", WorkbenchEvent.target_id == item_id).order_by(WorkbenchEvent.created_at.desc(), WorkbenchEvent.id.desc())).all()
    return [map_workbench_event(row) for row in rows]


@app.post("/api/work-items/{item_id}/comments")
def comment_work_item(item_id: str, payload: CommentAction, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    item = db.get(WorkItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")
    try:
        assert_project_visible(db, user, item.project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not payload.comment.strip():
        raise HTTPException(status_code=400, detail="comment is required")
    event = add_workbench_event(db, project_id=item.project_id, target_type="work_item", target_id=item.id, action="comment", actor=user, comment=payload.comment.strip())
    item.updated_at = datetime.now(timezone.utc)
    write_audit(db, user["name"], "comment_work_item", "work_item", item_id, {"comment": payload.comment.strip()})
    db.commit()
    return map_workbench_event(event)


@app.post("/api/work-items/{item_id}/cancel")
def cancel_work_item(item_id: str, payload: WorkItemAction | None = None, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    item = db.get(WorkItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")
    try:
        assert_project_visible(db, user, item.project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if item.status == "已完成":
        raise HTTPException(status_code=409, detail="Completed work item cannot be cancelled")
    assert_work_item_actor(item, user, "cancel")
    item.status = "已取消"
    item.updated_at = datetime.now(timezone.utc)
    comment = payload.comment if payload else None
    add_workbench_event(db, project_id=item.project_id, target_type="work_item", target_id=item.id, action="cancel", actor=user, comment=comment)
    write_audit(db, user["name"], "cancel_work_item", "work_item", item_id, {"comment": comment})
    db.commit()
    return {"id": item.id, "status": item.status}


@app.get("/api/review-tasks/{task_id}/events")
def list_review_task_events(task_id: str, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> list[dict]:
    task = db.get(ReviewTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Review task not found")
    try:
        assert_project_visible(db, user, task.project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    rows = db.scalars(select(WorkbenchEvent).where(WorkbenchEvent.target_type == "review_task", WorkbenchEvent.target_id == task_id).order_by(WorkbenchEvent.created_at.desc(), WorkbenchEvent.id.desc())).all()
    return [map_workbench_event(row) for row in rows]


@app.post("/api/review-tasks/{task_id}/comments")
def comment_review_task(task_id: str, payload: CommentAction, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    task = db.get(ReviewTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Review task not found")
    try:
        assert_project_visible(db, user, task.project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not payload.comment.strip():
        raise HTTPException(status_code=400, detail="comment is required")
    assert_review_task_actor(task, user, "comment")
    event = add_workbench_event(db, project_id=task.project_id, target_type="review_task", target_id=task.id, action="comment", actor=user, comment=payload.comment.strip())
    task.updated_at = datetime.now(timezone.utc)
    write_audit(db, user["name"], "comment_review_task", "review_task", task_id, {"comment": payload.comment.strip()})
    db.commit()
    return map_workbench_event(event)


@app.post("/api/review-tasks/{task_id}/assign")
def assign_review_task(task_id: str, payload: ReviewAction, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    if not payload.reviewerId:
        raise HTTPException(status_code=400, detail="reviewerId is required")
    task = db.get(ReviewTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Review task not found")
    try:
        assert_project_visible(db, user, task.project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    assert_review_task_actor(task, user, "assign")
    reviewer = db.get(AppUser, payload.reviewerId)
    if not reviewer or reviewer.status != "启用":
        raise HTTPException(status_code=404, detail="Reviewer not found or disabled")
    task.reviewer_id = reviewer.id
    task.status = "审核中"
    task.updated_at = datetime.now(timezone.utc)
    add_workbench_event(db, project_id=task.project_id, target_type="review_task", target_id=task.id, action="assign", actor=user, comment=payload.comment, payload={"reviewerId": reviewer.id, "reviewerName": reviewer.name})
    db.add(Notification(id=f"NT-{int(time.time() * 1000)}", user_id=reviewer.id, project_id=task.project_id, level="info", title=f"审核任务分配：{task.title}", message=payload.comment or "请及时处理该审核任务。", route=task.route, source_type="review_task", source_id=task.id, status="未读"))
    write_audit(db, user["name"], "assign_review_task", "review_task", task_id, {"reviewerId": reviewer.id, "comment": payload.comment})
    db.commit()
    return {"id": task.id, "status": task.status, "reviewerId": task.reviewer_id}


@app.post("/api/review-tasks/{task_id}/countersign")
def countersign_review_task(task_id: str, payload: ReviewAction, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    task = db.get(ReviewTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Review task not found")
    try:
        assert_project_visible(db, user, task.project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    assert_review_task_actor(task, user, "countersign")
    comment = payload.comment or "同意当前审核意见。"
    event = add_workbench_event(db, project_id=task.project_id, target_type="review_task", target_id=task.id, action="countersign", actor=user, comment=comment)
    task.status = "审核中"
    task.updated_at = datetime.now(timezone.utc)
    write_audit(db, user["name"], "countersign_review_task", "review_task", task_id, {"comment": comment})
    db.commit()
    return map_workbench_event(event)


@app.get("/api/notifications")
def list_notifications(
    status: str | None = None,
    projectId: str | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(current_user),
) -> list[dict]:
    if projectId:
        try:
            assert_project_visible(db, user, projectId)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
    stmt = select(Notification)
    if status:
        stmt = stmt.where(Notification.status == status)
    if projectId:
        stmt = stmt.where(Notification.project_id == projectId)
    if not _can_manage_workbench(user):
        stmt = stmt.where((Notification.user_id.is_(None)) | (Notification.user_id == user["id"]))
    rows = db.scalars(stmt.order_by(Notification.created_at.desc()).limit(100)).all()
    return [
        {
            "id": row.id,
            "level": row.level,
            "title": row.title,
            "message": row.message,
            "route": row.route,
            "status": row.status,
            "projectId": row.project_id,
            "sourceType": row.source_type,
            "sourceId": row.source_id,
            "createdAt": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@app.get("/api/notification-subscriptions")
def list_notification_subscriptions(db: Session = Depends(get_db), user: dict = Depends(current_user)) -> list[dict]:
    rows = db.scalars(select(NotificationSubscription).where(NotificationSubscription.user_id == user["id"]).order_by(NotificationSubscription.event_type)).all()
    by_type = {row.event_type: map_subscription(row) for row in rows}
    defaults = _default_subscriptions(user)
    return [by_type.get(item["eventType"], item) for item in defaults]


@app.put("/api/notification-subscriptions/{event_type}")
def update_notification_subscription(event_type: str, payload: NotificationSubscriptionUpdate, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    row = db.get(NotificationSubscription, {"user_id": user["id"], "event_type": event_type})
    now = datetime.now(timezone.utc)
    if not row:
        row = NotificationSubscription(user_id=user["id"], event_type=event_type, enabled=payload.enabled, delivery=payload.delivery, updated_at=now)
        db.add(row)
    else:
        row.enabled = payload.enabled
        row.delivery = payload.delivery
        row.updated_at = now
    write_audit(db, user["name"], "update_notification_subscription", "notification_subscription", event_type, {"enabled": payload.enabled, "delivery": payload.delivery})
    db.commit()
    return map_subscription(row)


@app.post("/api/notifications/read-all")
def mark_notifications_read_all(payload: NotificationBatchAction | None = None, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    stmt = select(Notification).where(Notification.status == "未读")
    if payload and payload.projectId:
        try:
            assert_project_visible(db, user, payload.projectId)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        stmt = stmt.where(Notification.project_id == payload.projectId)
    if not any(keyword in user.get("role", "") for keyword in ("管理员", "负责人", "领导", "审核", "经理")):
        stmt = stmt.where((Notification.user_id.is_(None)) | (Notification.user_id == user["id"]))
    rows = db.scalars(stmt).all()
    now = datetime.now(timezone.utc)
    for note in rows:
        note.status = "已读"
        note.read_at = now
        note.updated_at = now
    write_audit(db, user["name"], "read_all_notifications", "notification", payload.projectId if payload else None, {"count": len(rows)})
    db.commit()
    return {"count": len(rows), "status": "已读"}


@app.post("/api/notifications/{notification_id}/archive")
def archive_notification(notification_id: str, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    note = db.get(Notification, notification_id)
    if not note:
        raise HTTPException(status_code=404, detail="Notification not found")
    try:
        assert_project_visible(db, user, note.project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if note.user_id and note.user_id != user["id"]:
        raise HTTPException(status_code=403, detail="Notification belongs to another user")
    note.status = "已归档"
    note.updated_at = datetime.now(timezone.utc)
    write_audit(db, user["name"], "archive_notification", "notification", notification_id, {})
    db.commit()
    return {"id": note.id, "status": note.status}


@app.get("/api/tasks/{task_id}/events")
def list_task_events(task_id: str, taskKind: str, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> list[dict]:
    rows = db.scalars(select(TaskEvent).where(TaskEvent.task_kind == taskKind, TaskEvent.task_id == task_id).order_by(TaskEvent.created_at.desc(), TaskEvent.id.desc())).all()
    if rows:
        try:
            assert_project_visible(db, user, rows[0].project_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
    return [map_task_event(row) for row in rows]


@app.post("/api/work-items/{item_id}/claim")
def claim_work_item(item_id: str, payload: WorkItemAction | None = None, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    item = db.get(WorkItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")
    try:
        assert_project_visible(db, user, item.project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if item.status in {"已完成", "已取消"}:
        raise HTTPException(status_code=409, detail="Work item is already closed")
    assert_work_item_actor(item, user, "claim")
    assignee_id = (payload.assigneeId if payload else None) or user["id"]
    item.assignee_id = assignee_id
    item.status = "处理中"
    item.updated_at = datetime.now(timezone.utc)
    add_workbench_event(db, project_id=item.project_id, target_type="work_item", target_id=item.id, action="claim", actor=user, comment=payload.comment if payload else None, payload={"assigneeId": assignee_id})
    write_audit(db, user["name"], "claim_work_item", "work_item", item_id, {"assigneeId": assignee_id})
    db.commit()
    return {"id": item.id, "status": item.status, "assigneeId": item.assignee_id}


@app.post("/api/work-items/{item_id}/complete")
def complete_work_item(item_id: str, payload: WorkItemAction | None = None, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    item = db.get(WorkItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")
    try:
        assert_project_visible(db, user, item.project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if item.status in {"已完成", "已取消"}:
        return {"id": item.id, "status": item.status}
    assert_work_item_actor(item, user, "complete")
    item.status = "已完成"
    item.assignee_id = item.assignee_id or user["id"]
    item.completed_at = datetime.now(timezone.utc)
    item.updated_at = item.completed_at
    add_workbench_event(db, project_id=item.project_id, target_type="work_item", target_id=item.id, action="complete", actor=user, comment=payload.comment if payload else None)
    write_audit(db, user["name"], "complete_work_item", "work_item", item_id, {"comment": payload.comment if payload else None})
    db.commit()
    return {"id": item.id, "status": item.status}


@app.post("/api/work-items/{item_id}/transfer")
def transfer_work_item(item_id: str, payload: WorkItemAction, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    if not payload.assigneeId:
        raise HTTPException(status_code=400, detail="assigneeId is required")
    item = db.get(WorkItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")
    try:
        assert_project_visible(db, user, item.project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    assert_work_item_actor(item, user, "transfer")
    target = db.get(AppUser, payload.assigneeId)
    if not target or target.status != "启用":
        raise HTTPException(status_code=404, detail="Target user not found or disabled")
    item.assignee_id = payload.assigneeId
    item.status = "待处理"
    item.updated_at = datetime.now(timezone.utc)
    add_workbench_event(db, project_id=item.project_id, target_type="work_item", target_id=item.id, action="transfer", actor=user, comment=payload.comment, payload={"assigneeId": payload.assigneeId})
    db.add(Notification(id=f"NT-{int(time.time() * 1000)}", user_id=payload.assigneeId, project_id=item.project_id, level="info", title=f"工作项转交：{item.title}", message=payload.comment or "请及时处理该工作项。", route=item.route, source_type="work_item", source_id=item.id, status="未读"))
    write_audit(db, user["name"], "transfer_work_item", "work_item", item_id, {"assigneeId": payload.assigneeId, "comment": payload.comment})
    db.commit()
    return {"id": item.id, "status": item.status, "assigneeId": item.assignee_id}


@app.post("/api/review-tasks/{task_id}/approve")
def approve_review_task(task_id: str, payload: ReviewAction | None = None, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    task = db.get(ReviewTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Review task not found")
    try:
        assert_project_visible(db, user, task.project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    assert_review_task_actor(task, user, "approve")
    try:
        assert_review_approval_gate(db, task)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    task.status = "已通过"
    task.reviewer_id = task.reviewer_id or user["id"]
    task.decision = "approved"
    task.comment = payload.comment if payload else None
    task.decided_at = datetime.now(timezone.utc)
    task.updated_at = task.decided_at
    add_workbench_event(db, project_id=task.project_id, target_type="review_task", target_id=task.id, action="approve", actor=user, comment=task.comment, payload={"targetType": task.target_type, "targetId": task.target_id})
    if task.target_type == "report_chapter":
        chapter = db.get(ReportChapter, task.target_id)
        if chapter:
            chapter.status = "已审核"
    elif task.target_type == "investment_estimate":
        estimate = db.get(InvestmentEstimate, task.target_id)
        if estimate:
            estimate.status = "confirmed"
            estimate.confirmed_by = user["name"]
            estimate.confirmed_at = task.decided_at
            estimate.updated_at = task.decided_at
    write_audit(db, user["name"], "approve_review_task", "review_task", task_id, {"targetType": task.target_type, "targetId": task.target_id, "comment": task.comment})
    db.commit()
    return {"id": task.id, "status": task.status, "decision": task.decision}


@app.post("/api/review-tasks/{task_id}/reject")
def reject_review_task(task_id: str, payload: ReviewAction | None = None, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    task = db.get(ReviewTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Review task not found")
    try:
        assert_project_visible(db, user, task.project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    assert_review_task_actor(task, user, "reject")
    task.status = "已退回"
    task.reviewer_id = task.reviewer_id or user["id"]
    task.decision = "rejected"
    task.comment = payload.comment if payload else "请修改后重新提交审核。"
    task.decided_at = datetime.now(timezone.utc)
    task.updated_at = task.decided_at
    if task.target_type == "report_chapter":
        chapter = db.get(ReportChapter, task.target_id)
        if chapter:
            chapter.status = "编制中"
    elif task.target_type == "investment_estimate":
        estimate = db.get(InvestmentEstimate, task.target_id)
        if estimate:
            estimate.status = "draft"
            estimate.updated_at = task.decided_at
    db.add(Notification(
        id=f"NT-{int(time.time() * 1000)}",
        user_id=None,
        project_id=task.project_id,
        level="warning",
        title=f"审核退回：{task.title}",
        message=task.comment,
        route=task.route,
        source_type="review_task",
        source_id=task.id,
        status="未读",
    ))
    write_audit(db, user["name"], "reject_review_task", "review_task", task_id, {"targetType": task.target_type, "targetId": task.target_id, "comment": task.comment})
    db.commit()
    return {"id": task.id, "status": task.status, "decision": task.decision, "comment": task.comment}


@app.post("/api/notifications/{notification_id}/read")
def mark_notification_read(notification_id: str, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    note = db.get(Notification, notification_id)
    if not note:
        raise HTTPException(status_code=404, detail="Notification not found")
    try:
        assert_project_visible(db, user, note.project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if note.user_id and note.user_id != user["id"]:
        raise HTTPException(status_code=403, detail="Notification belongs to another user")
    note.status = "已读"
    note.read_at = datetime.now(timezone.utc)
    note.updated_at = note.read_at
    write_audit(db, user["name"], "read_notification", "notification", notification_id, {})
    db.commit()
    return {"id": note.id, "status": note.status}


@app.post("/api/tasks/{task_id}/cancel")
def cancel_background_task(task_id: str, payload: TaskAction, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    now = datetime.now(timezone.utc)
    task_project_id = None
    revoke_result = revoke_task(task_id, terminate=payload.force)
    if payload.taskKind == "parse":
        job = db.get(ParseJob, task_id)
        if not job:
            raise HTTPException(status_code=404, detail="Parse job not found")
        document = db.get(ProjectDocument, job.document_id) if job.document_id else None
        try:
            assert_project_visible(db, user, document.project_id if document else None)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        job.status = "cancelled"
        job.message = "用户取消解析任务。"
        job.updated_at = now
        task_project_id = document.project_id if document else None
        if document and document.parse_status != "已解析":
            document.parse_status = "需复核"
            document.updated_at = current_day(db)
    elif payload.taskKind == "quality":
        job = db.get(QualityCheckJob, task_id)
        if not job:
            raise HTTPException(status_code=404, detail="Quality check job not found")
        try:
            assert_project_visible(db, user, job.project_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        task_project_id = job.project_id
        job.status = "cancelled"
        job.message = "用户取消质量检查任务。"
        job.updated_at = now
    elif payload.taskKind == "artifact":
        artifact = db.get(Artifact, task_id)
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
        try:
            assert_project_visible(db, user, artifact.project_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        task_project_id = artifact.project_id
        artifact.status = "受阻"
        artifact.updated_at = current_day(db)
    else:
        raise HTTPException(status_code=400, detail="Unsupported taskKind")
    stage = "强制终止" if payload.force else "用户取消"
    message = "已登记强制终止请求。" if payload.force else "已登记取消请求。"
    add_task_event(db, project_id=task_project_id, task_kind=payload.taskKind, task_id=task_id, status="cancelled", stage=stage, message=message, actor=user, payload={**revoke_result, "force": payload.force})
    write_audit(db, user["name"], "cancel_background_task", payload.taskKind, task_id, {"revoke": revoke_result, "force": payload.force})
    db.commit()
    return {"id": task_id, "taskKind": payload.taskKind, "status": "cancelled", "force": payload.force, "revoke": revoke_result}


@app.post("/api/tasks/{task_id}/retry", status_code=202)
def retry_background_task(task_id: str, payload: TaskAction, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    if payload.taskKind == "parse":
        old_job = db.get(ParseJob, task_id)
        if not old_job or not old_job.document_id:
            raise HTTPException(status_code=404, detail="Parse job not found")
        document = db.get(ProjectDocument, old_job.document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        try:
            assert_project_visible(db, user, document.project_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        job = ParseJob(id=f"JOB-{int(time.time() * 1000)}", document_id=document.id, status="queued", message=f"由 {task_id} 重试创建。", result={})
        document.parse_status = "解析中"
        document.updated_at = current_day(db)
        db.add(job)
        db.commit()
        result = enqueue_or_run(parse_document_task, (document.id, job.id), lambda: parse_document(db, document.id, job.id) or {"status": "not_found"})
        add_task_event(db, project_id=document.project_id, task_kind="parse", task_id=job.id, status="queued", stage="重试提交", message=f"由 {task_id} 重试创建。", actor=user, payload={"retryOf": task_id, "execution": result.get("execution")})
        write_audit(db, user["name"], "retry_background_task", "parse", job.id, {"retryOf": task_id})
        db.commit()
        return {"id": job.id, "taskKind": "parse", "status": "queued", **result}
    if payload.taskKind == "quality":
        old_job = db.get(QualityCheckJob, task_id)
        if not old_job:
            raise HTTPException(status_code=404, detail="Quality check job not found")
        try:
            assert_project_visible(db, user, old_job.project_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        result = enqueue_or_run(quality_check_task, (old_job.project_id,), lambda: run_quality_check(db, old_job.project_id))
        add_task_event(db, project_id=old_job.project_id, task_kind="quality", task_id=result.get("taskId", task_id), status="queued", stage="重试提交", message="质量检查任务已重新提交。", actor=user, payload={"retryOf": task_id, "execution": result.get("execution")})
        write_audit(db, user["name"], "retry_background_task", "quality", task_id, {"projectId": old_job.project_id})
        db.commit()
        return {"id": result.get("taskId", task_id), "taskKind": "quality", "status": "queued", **result}
    if payload.taskKind == "artifact":
        artifact = db.get(Artifact, task_id)
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
        try:
            assert_project_visible(db, user, artifact.project_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        artifact.status = "生成中"
        artifact.updated_at = current_day(db)
        db.commit()
        result = enqueue_or_run(export_artifact_task, (artifact.id,), lambda: {"artifact": map_artifact(generate_artifact(db, artifact.id))})
        add_task_event(db, project_id=artifact.project_id, task_kind="artifact", task_id=artifact.id, status="queued", stage="重试提交", message="成果导出任务已重新提交。", actor=user, payload={"retryOf": task_id, "execution": result.get("execution")})
        write_audit(db, user["name"], "retry_background_task", "artifact", task_id, {})
        db.commit()
        return {"id": artifact.id, "taskKind": "artifact", "status": "queued", **result}
    raise HTTPException(status_code=400, detail="Unsupported taskKind")


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


@app.get("/api/project-center")
def project_center(db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    return build_project_center(db, user)


@app.get("/api/project-drafts")
def get_project_drafts(db: Session = Depends(get_db), user: dict = Depends(current_user)) -> list[dict]:
    return list_project_drafts(db, user)


@app.post("/api/project-drafts", status_code=201)
def save_project_draft(payload: ProjectDraftInput, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    row = upsert_project_draft(db, user, payload.payload, payload.id, payload.step, payload.name)
    write_audit(db, user["name"], "save_project_draft", "project_wizard_draft", row.id, {"step": payload.step, "name": payload.name})
    db.commit()
    return map_project_draft(row)


@app.delete("/api/project-drafts/{draft_id}")
def delete_project_draft(draft_id: str, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    row = db.get(ProjectWizardDraft, draft_id)
    if not row or row.user_id != user.get("id"):
        raise HTTPException(status_code=404, detail="Project draft not found")
    row.status = "已删除"
    row.updated_at = datetime.now(timezone.utc)
    write_audit(db, user["name"], "delete_project_draft", "project_wizard_draft", draft_id, {})
    db.commit()
    return {"id": draft_id, "status": row.status}


@app.get("/api/project-region-rules")
def get_project_region_rules(db: Session = Depends(get_db), _: dict = Depends(current_user)) -> list[dict]:
    return list_region_rules(db)


@app.post("/api/project-region-rules", status_code=201)
def upsert_project_region_rule(payload: ProjectRegionRuleInput, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    if not is_management_role(user.get("role")):
        raise HTTPException(status_code=403, detail="仅管理角色可维护地区规则")
    rule_id = payload.id or f"PRR-{int(time.time() * 1000)}"
    row = db.get(ProjectRegionRule, rule_id)
    if not row:
        row = ProjectRegionRule(
            id=rule_id,
            name=payload.name,
            region=payload.region,
            project_type=payload.projectType,
            version=payload.version,
            status=payload.status,
            description=payload.description,
            materials=payload.materials,
            facts=payload.facts,
            chapters=payload.chapters,
            artifacts=payload.artifacts,
            settings=payload.settings,
        )
        db.add(row)
    else:
        row.name = payload.name
        row.region = payload.region
        row.project_type = payload.projectType
        row.version = payload.version
        row.status = payload.status
        row.description = payload.description
        row.materials = payload.materials
        row.facts = payload.facts
        row.chapters = payload.chapters
        row.artifacts = payload.artifacts
        row.settings = payload.settings
        row.updated_at = datetime.now(timezone.utc)
    write_audit(db, user["name"], "upsert_project_region_rule", "project_region_rule", row.id, payload.model_dump())
    db.commit()
    return map_region_rule(row)


@app.get("/api/projects")
def list_projects(db: Session = Depends(get_db), user: dict = Depends(current_user)) -> list[dict]:
    return build_project_center(db, user)["projects"]


@app.post("/api/projects", status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    template = db.get(ReportTemplate, payload.templateId) if payload.templateId else None
    project = Project(
        id=f"P{int(time.time() * 1000)}",
        name=payload.name.strip(),
        type=payload.type or "可行性研究报告",
        location=payload.location or "待补充",
        phase="项目建档",
        owner=payload.owner or user.get("name") or "项目负责人",
        code=payload.code or generate_project_code(db, payload.type),
        status="建档中",
        confidentiality=payload.confidentiality or "内部",
        template_id=payload.templateId or (template.id if template else None),
        template_version=payload.templateVersion or (template.version if template else None),
        region=payload.region or payload.location or "待补充",
        region_rule_id=payload.regionRuleId or "BUILTIN-COMMON",
        initialization_rule_version=None,
        draft_source_id=payload.draftId,
        planned_start=payload.plannedStart,
        planned_end=payload.plannedEnd,
        description=payload.description,
        progress=8,
        risk="一般",
        archived_at=None,
    )
    apply_project_defaults(project, template)
    db.add(project)
    # Add creator as project lead. Additional members from the wizard are optional.
    ensure_project_member(db, project.id, user["id"], "项目负责人")
    for member in payload.members:
        user_id = member.get("userId")
        if user_id:
            ensure_project_member(db, project.id, user_id, member.get("role") or "项目成员")
    if payload.milestones:
        for index, item in enumerate(payload.milestones, start=1):
            if not item.get("name"):
                continue
            db.add(ProjectMilestone(
                id=f"PM-{project.id}-{index}",
                project_id=project.id,
                name=item.get("name"),
                owner=item.get("owner") or project.owner,
                status=item.get("status") or "未开始",
                due_at=item.get("dueAt"),
                completed_at=None,
                sort_order=item.get("sortOrder") or index,
            ))
    else:
        add_default_milestones(db, project)
    ensure_project_initialization_package(db, project, user)
    if payload.draftId:
        draft = db.get(ProjectWizardDraft, payload.draftId)
        if draft and draft.user_id == user.get("id"):
            draft.status = "已使用"
            draft.updated_at = datetime.now(timezone.utc)
    write_audit(db, user["name"], "create_project", "project", project.id, payload.model_dump())
    db.commit()
    return map_project_profile(db, project, user)


@app.get("/api/projects/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        assert_project_visible(db, user, project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return map_project_profile(db, project, user)


@app.patch("/api/projects/{project_id}")
def update_project(project_id: str, payload: ProjectUpdate, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        assert_project_visible(db, user, project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not is_management_role(user.get("role")) and project.owner != user.get("name"):
        raise HTTPException(status_code=403, detail="仅项目负责人或管理角色可修改项目基本信息")
    fields = payload.model_dump(exclude_none=True)
    mapping = {"templateId": "template_id", "templateVersion": "template_version", "regionRuleId": "region_rule_id", "draftId": "draft_source_id", "plannedStart": "planned_start", "plannedEnd": "planned_end"}
    for key, value in fields.items():
        attr = mapping.get(key, key)
        setattr(project, attr, value)
    if payload.progress is not None:
        project.progress = max(0, min(100, payload.progress))
    project.updated_at = datetime.now(timezone.utc)
    write_audit(db, user["name"], "update_project", "project", project.id, fields)
    db.commit()
    return map_project_profile(db, project, user)


@app.post("/api/projects/{project_id}/members", status_code=201)
def add_project_member(project_id: str, payload: ProjectMemberInput, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        assert_project_visible(db, user, project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not is_management_role(user.get("role")) and project.owner != user.get("name"):
        raise HTTPException(status_code=403, detail="仅项目负责人或管理角色可维护成员")
    if not db.get(AppUser, payload.userId):
        raise HTTPException(status_code=404, detail="User not found")
    member = ensure_project_member(db, project_id, payload.userId, payload.role)
    project.updated_at = datetime.now(timezone.utc)
    write_audit(db, user["name"], "upsert_project_member", "project", project_id, payload.model_dump())
    db.commit()
    return map_project_profile(db, project, user)


@app.delete("/api/projects/{project_id}/members/{user_id}")
def remove_project_member(project_id: str, user_id: str, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        assert_project_visible(db, user, project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not is_management_role(user.get("role")) and project.owner != user.get("name"):
        raise HTTPException(status_code=403, detail="仅项目负责人或管理角色可维护成员")
    member = db.get(ProjectMember, {"project_id": project_id, "user_id": user_id})
    if not member:
        raise HTTPException(status_code=404, detail="Project member not found")
    db.delete(member)
    project.updated_at = datetime.now(timezone.utc)
    write_audit(db, user["name"], "remove_project_member", "project", project_id, {"userId": user_id})
    db.commit()
    return map_project_profile(db, project, user)


@app.post("/api/projects/{project_id}/milestones", status_code=201)
def add_project_milestone(project_id: str, payload: ProjectMilestoneInput, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        assert_project_visible(db, user, project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    row = ProjectMilestone(
        id=f"PM-{int(time.time() * 1000)}",
        project_id=project_id,
        name=payload.name.strip(),
        owner=payload.owner,
        status=payload.status,
        due_at=payload.dueAt,
        completed_at=datetime.now(timezone.utc) if payload.status == "已完成" else None,
        sort_order=payload.sortOrder or len(db.scalars(select(ProjectMilestone).where(ProjectMilestone.project_id == project_id)).all()) + 1,
    )
    db.add(row)
    project.updated_at = datetime.now(timezone.utc)
    write_audit(db, user["name"], "add_project_milestone", "project", project_id, payload.model_dump())
    db.commit()
    return map_project_profile(db, project, user)


@app.patch("/api/projects/{project_id}/milestones/{milestone_id}")
def update_project_milestone(project_id: str, milestone_id: str, payload: ProjectMilestoneInput, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    project = db.get(Project, project_id)
    row = db.get(ProjectMilestone, milestone_id)
    if not project or not row or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="Project milestone not found")
    try:
        assert_project_visible(db, user, project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    row.name = payload.name.strip()
    row.owner = payload.owner
    row.status = payload.status
    row.due_at = payload.dueAt
    row.sort_order = payload.sortOrder or row.sort_order
    row.completed_at = datetime.now(timezone.utc) if payload.status == "已完成" else None
    row.updated_at = datetime.now(timezone.utc)
    project.updated_at = row.updated_at
    write_audit(db, user["name"], "update_project_milestone", "project_milestone", milestone_id, payload.model_dump())
    db.commit()
    return map_project_profile(db, project, user)


@app.post("/api/projects/{project_id}/initialize", status_code=201)
def initialize_project_package(project_id: str, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        assert_project_visible(db, user, project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not is_management_role(user.get("role")) and project.owner != user.get("name"):
        raise HTTPException(status_code=403, detail="仅项目负责人或管理角色可初始化项目包")
    summary = ensure_project_initialization_package(db, project, user)
    write_audit(db, user["name"], "initialize_project_package", "project", project_id, summary)
    db.commit()
    return map_project_profile(db, project, user)


@app.patch("/api/projects/{project_id}/materials/{material_id}")
def update_project_material(project_id: str, material_id: str, payload: ProjectMaterialInput, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    project = db.get(Project, project_id)
    row = db.get(ProjectMaterialRequirement, material_id)
    if not project or not row or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="Project material requirement not found")
    try:
        assert_project_visible(db, user, project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not is_management_role(user.get("role")) and project.owner != user.get("name"):
        raise HTTPException(status_code=403, detail="仅项目负责人或管理角色可维护资料清单")
    if payload.status not in {"待上传", "已上传", "已确认", "不适用"}:
        raise HTTPException(status_code=400, detail="Unsupported material status")
    row.status = payload.status
    row.source_type = payload.sourceType
    row.source_id = payload.sourceId
    row.updated_at = datetime.now(timezone.utc)
    project.updated_at = row.updated_at
    write_audit(db, user["name"], "update_project_material", "project_material", material_id, payload.model_dump())
    db.commit()
    return map_project_profile(db, project, user)




@app.get("/api/projects/{project_id}/migration-preview")
def get_project_migration_preview(
    project_id: str,
    templateId: str | None = None,
    templateVersion: str | None = None,
    regionRuleId: str | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(current_user),
) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        assert_project_visible(db, user, project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return preview_project_rule_migration(db, project, templateId, templateVersion, regionRuleId)


@app.post("/api/projects/{project_id}/migration-plans", status_code=201)
def create_project_migration_plan(project_id: str, payload: ProjectMigrationPlanInput, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        assert_project_visible(db, user, project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not is_management_role(user.get("role")) and project.owner != user.get("name"):
        raise HTTPException(status_code=403, detail="仅项目负责人或管理角色可生成迁移计划")
    row = create_rule_migration_plan(db, project, user, payload.templateId, payload.templateVersion, payload.regionRuleId)
    write_audit(db, user["name"], "create_project_migration_plan", "project_rule_migration_plan", row.id, payload.model_dump())
    db.commit()
    return map_rule_migration_plan(row)


@app.post("/api/projects/{project_id}/migration-plans/{plan_id}/apply")
def apply_project_migration_plan(project_id: str, plan_id: str, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    project = db.get(Project, project_id)
    plan = db.get(ProjectRuleMigrationPlan, plan_id)
    if not project or not plan or plan.project_id != project_id:
        raise HTTPException(status_code=404, detail="Migration plan not found")
    try:
        assert_project_visible(db, user, project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not is_management_role(user.get("role")) and project.owner != user.get("name"):
        raise HTTPException(status_code=403, detail="仅项目负责人或管理角色可应用迁移计划")
    apply_rule_migration_plan(db, project, plan, user)
    write_audit(db, user["name"], "apply_project_migration_plan", "project_rule_migration_plan", plan.id, {"projectId": project_id})
    db.commit()
    return map_project_profile(db, project, user)


@app.post("/api/projects/{project_id}/revisions", status_code=201)
def create_project_revision_endpoint(project_id: str, payload: ProjectRevisionInput, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        assert_project_visible(db, user, project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not is_management_role(user.get("role")) and project.owner != user.get("name"):
        raise HTTPException(status_code=403, detail="仅项目负责人或管理角色可创建项目修订")
    row = create_project_revision(db, project, user, payload.title, payload.reason)
    write_audit(db, user["name"], "create_project_revision", "project_revision", row.id, payload.model_dump())
    db.commit()
    return map_project_revision(row)


@app.post("/api/projects/{project_id}/revisions/{revision_id}/close")
def close_project_revision_endpoint(project_id: str, revision_id: str, payload: ProjectRevisionCloseInput, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    project = db.get(Project, project_id)
    revision = db.get(ProjectRevision, revision_id)
    if not project or not revision or revision.project_id != project_id:
        raise HTTPException(status_code=404, detail="Project revision not found")
    try:
        assert_project_visible(db, user, project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not is_management_role(user.get("role")) and project.owner != user.get("name"):
        raise HTTPException(status_code=403, detail="仅项目负责人或管理角色可关闭项目修订")
    close_project_revision(db, revision, user, payload.status)
    write_audit(db, user["name"], "close_project_revision", "project_revision", revision.id, payload.model_dump())
    db.commit()
    return map_project_revision(revision)


@app.get("/api/projects/{project_id}/status-gate")
def get_project_status_gate(project_id: str, targetStatus: str = "已关闭", db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        assert_project_visible(db, user, project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return evaluate_project_status_gate(db, project, targetStatus)


@app.post("/api/projects/{project_id}/status")
def change_project_status(project_id: str, payload: ProjectStatusAction, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        assert_project_visible(db, user, project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not is_management_role(user.get("role")) and project.owner != user.get("name"):
        raise HTTPException(status_code=403, detail="仅项目负责人或管理角色可变更项目状态")
    if not can_change_status(project, payload.status):
        raise HTTPException(status_code=409, detail=f"当前状态不允许变更为 {payload.status}")
    gate = evaluate_project_status_gate(db, project, payload.status)
    if payload.status in {"已关闭", "已归档"} and not gate["allowed"]:
        raise HTTPException(status_code=409, detail={"message": "项目状态门禁未通过", "gate": gate})
    project.status = payload.status
    if payload.status == "已归档":
        project.archived_at = datetime.now(timezone.utc)
    if payload.status == "已关闭":
        project.phase = "项目关闭"
    if payload.status == "已归档":
        project.phase = "成果归档"
    if payload.status == "进行中" and project.phase in {"项目关闭", "成果归档", "项目建档"}:
        project.phase = "资料清点"
    project.updated_at = datetime.now(timezone.utc)
    write_audit(db, user["name"], "change_project_status", "project", project_id, payload.model_dump())
    db.commit()
    return map_project_profile(db, project, user)


@app.post("/api/projects/{project_id}/copy", status_code=201)
def copy_project(project_id: str, payload: ProjectCopyAction, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    source = db.get(Project, project_id)
    if not source:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        assert_project_visible(db, user, project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    clone = Project(
        id=f"P{int(time.time() * 1000)}",
        name=payload.name or f"{source.name}-复制",
        type=source.type,
        location=source.location,
        phase="项目建档",
        owner=user.get("name") or source.owner,
        code=generate_project_code(db, source.type),
        status="建档中",
        confidentiality=source.confidentiality if payload.copySettings else "内部",
        template_id=source.template_id if payload.copySettings else None,
        template_version=source.template_version if payload.copySettings else None,
        region=source.region if payload.copySettings else source.location,
        region_rule_id=source.region_rule_id if payload.copySettings else "BUILTIN-COMMON",
        initialization_rule_version=None,
        draft_source_id=None,
        planned_start=None,
        planned_end=None,
        description=f"由 {source.name} 复制创建。",
        progress=8,
        risk="一般",
        archived_at=None,
    )
    db.add(clone)
    ensure_project_member(db, clone.id, user["id"], "项目负责人")
    if payload.copyMembers:
        for member in db.scalars(select(ProjectMember).where(ProjectMember.project_id == source.id)).all():
            ensure_project_member(db, clone.id, member.user_id, member.role)
    if payload.copyMilestones:
        for index, milestone in enumerate(db.scalars(select(ProjectMilestone).where(ProjectMilestone.project_id == source.id).order_by(ProjectMilestone.sort_order)).all(), start=1):
            db.add(ProjectMilestone(id=f"PM-{clone.id}-{index}", project_id=clone.id, name=milestone.name, owner=milestone.owner, status="未开始", due_at=None, completed_at=None, sort_order=index))
    else:
        add_default_milestones(db, clone)
    ensure_project_initialization_package(db, clone, user)
    write_audit(db, user["name"], "copy_project", "project", clone.id, {"sourceProjectId": project_id, **payload.model_dump()})
    db.commit()
    return map_project_profile(db, clone, user)


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
def export_artifact(artifact_id: str, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    artifact.status = "生成中"
    artifact.updated_at = current_day(db)
    add_task_event(db, project_id=artifact.project_id, task_kind="artifact", task_id=artifact.id, status="queued", stage="提交导出", message="成果导出任务已提交。", actor=user, payload={"format": artifact.format})
    write_audit(db, user["name"], "queue_artifact_export", "artifact", artifact_id, {"format": artifact.format})
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
def run_parse(document_id: str, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    document = db.get(ProjectDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    job = ParseJob(id=f"JOB-{int(time.time() * 1000)}", document_id=document_id, status="queued", message="解析任务已进入后台处理。", result={})
    document.parse_status = "解析中"
    document.updated_at = current_day(db)
    db.add(job)
    add_task_event(db, project_id=document.project_id, task_kind="parse", task_id=job.id, status="queued", stage="提交解析", message="资料解析任务已提交。", actor=user, payload={"documentId": document_id})
    write_audit(db, user["name"], "queue_document_parse", "project_document", document_id, {"jobId": job.id})
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
def create_quality_check(payload: QualityCheckCreate, db: Session = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    if not payload.projectId:
        return run_quality_check(db, payload.projectId)
    result = enqueue_or_run(quality_check_task, (payload.projectId,), lambda: run_quality_check(db, payload.projectId))
    add_task_event(db, project_id=payload.projectId, task_kind="quality", task_id=result.get("taskId", f"QC-{int(time.time() * 1000)}"), status="queued", stage="提交检查", message="质量检查任务已提交。", actor=user, payload={"execution": result.get("execution")})
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
    return {
        "id": row.id,
        "code": getattr(row, "code", None) or row.id,
        "name": row.name,
        "type": row.type,
        "location": row.location,
        "phase": row.phase,
        "owner": row.owner,
        "status": getattr(row, "status", None) or "进行中",
        "confidentiality": getattr(row, "confidentiality", None) or "内部",
        "templateId": getattr(row, "template_id", None),
        "templateVersion": getattr(row, "template_version", None),
        "plannedStart": getattr(row, "planned_start", None),
        "plannedEnd": getattr(row, "planned_end", None),
        "description": getattr(row, "description", None),
        "progress": row.progress,
        "risk": row.risk,
        "archivedAt": row.archived_at.isoformat() if getattr(row, "archived_at", None) else None,
    }


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
