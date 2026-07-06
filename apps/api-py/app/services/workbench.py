from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AppUser,
    FactItem,
    InvestmentEstimate,
    Notification,
    Project,
    ProjectDocument,
    ProjectMember,
    QualityIssue,
    ReportChapter,
    ReviewTask,
    TaskEvent,
    WorkbenchEvent,
    WorkItem,
)

MANAGEMENT_KEYWORDS = ("管理员", "负责人", "领导", "审核", "经理")
ACTIVE_WORK_STATUSES = {"待领取", "待处理", "处理中"}
ACTIVE_REVIEW_STATUSES = {"待审核", "审核中"}
SEVERITY_PRIORITY = {"阻断": "P0", "严重": "P0", "一般": "P1", "提示": "P2"}


def is_management_role(role: str | None) -> bool:
    return any(keyword in (role or "") for keyword in MANAGEMENT_KEYWORDS)


def visible_project_ids(db: Session, user: dict[str, Any]) -> set[str] | None:
    """Return None for management/global roles, otherwise project ids visible to the user."""
    if is_management_role(user.get("role")):
        return None
    user_id = user.get("id")
    user_name = user.get("name")
    member_project_ids = set()
    if user_id:
        member_project_ids.update(
            db.scalars(select(ProjectMember.project_id).where(ProjectMember.user_id == user_id)).all()
        )
    if user_name:
        member_project_ids.update(db.scalars(select(Project.id).where(Project.owner == user_name)).all())
    return member_project_ids


def apply_project_visibility(projects: Iterable[Project], visible_ids: set[str] | None) -> list[Project]:
    items = list(projects)
    if visible_ids is None:
        return items
    return [project for project in items if project.id in visible_ids]


def assert_project_visible(db: Session, user: dict[str, Any], project_id: str | None) -> None:
    if not project_id or is_management_role(user.get("role")):
        return
    visible = visible_project_ids(db, user)
    if visible is not None and project_id not in visible:
        raise PermissionError("当前用户无权访问该项目")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{int(time.time() * 1000)}"


def _find_work_item(db: Session, source_type: str, source_id: str) -> WorkItem | None:
    fake_rows = getattr(db, "rows_by_model", None)
    if fake_rows is not None:
        return next((item for item in fake_rows.get(WorkItem, []) if item.source_type == source_type and item.source_id == source_id), None)
    return db.scalar(select(WorkItem).where(WorkItem.source_type == source_type, WorkItem.source_id == source_id))


def _find_review_task(db: Session, target_type: str, target_id: str) -> ReviewTask | None:
    fake_rows = getattr(db, "rows_by_model", None)
    if fake_rows is not None:
        return next((item for item in fake_rows.get(ReviewTask, []) if item.target_type == target_type and item.target_id == target_id), None)
    return db.scalar(select(ReviewTask).where(ReviewTask.target_type == target_type, ReviewTask.target_id == target_id))


def _find_notification(db: Session, source_type: str, source_id: str, user_id: str | None = None) -> Notification | None:
    fake_rows = getattr(db, "rows_by_model", None)
    if fake_rows is not None:
        return next((item for item in fake_rows.get(Notification, []) if item.source_type == source_type and item.source_id == source_id and (not user_id or item.user_id == user_id)), None)
    stmt = select(Notification).where(Notification.source_type == source_type, Notification.source_id == source_id)
    if user_id:
        stmt = stmt.where(Notification.user_id == user_id)
    return db.scalar(stmt)


def _upsert_work_item(db: Session, *, source_type: str, source_id: str, project_id: str | None, category: str,
                      title: str, detail: str, priority: str, owner: str, route: str, created_by: str | None) -> None:
    item = _find_work_item(db, source_type, source_id)
    if item and item.status in {"已完成", "已取消"}:
        return
    if not item:
        item = WorkItem(
            id=_new_id("WI"),
            project_id=project_id,
            source_type=source_type,
            source_id=source_id,
            category=category,
            title=title,
            detail=detail,
            priority=priority,
            status="待处理",
            owner=owner,
            assignee_id=None,
            due_at=None,
            route=route,
            created_by=created_by,
        )
        db.add(item)
    else:
        item.project_id = project_id
        item.category = category
        item.title = title
        item.detail = detail
        item.priority = priority
        item.owner = owner
        item.route = route
        item.updated_at = _now()


def _upsert_review_task(db: Session, *, target_type: str, target_id: str, project_id: str | None, title: str,
                        description: str, priority: str, submitter: str, route: str) -> None:
    task = _find_review_task(db, target_type, target_id)
    if task and task.status in {"已通过", "已退回", "已取消"}:
        return
    if not task:
        task = ReviewTask(
            id=_new_id("RT"),
            project_id=project_id,
            target_type=target_type,
            target_id=target_id,
            title=title,
            description=description,
            priority=priority,
            status="待审核",
            submitter=submitter,
            reviewer_id=None,
            route=route,
            due_at=None,
            decision=None,
            comment=None,
            decided_at=None,
        )
        db.add(task)
    else:
        task.project_id = project_id
        task.title = title
        task.description = description
        task.priority = priority
        task.submitter = submitter
        task.route = route
        task.updated_at = _now()


def _upsert_notification(db: Session, *, source_type: str, source_id: str, project_id: str | None, level: str,
                         title: str, message: str, route: str, user_id: str | None = None) -> None:
    note = _find_notification(db, source_type, source_id, user_id)
    if not note:
        db.add(
            Notification(
                id=_new_id("NT"),
                user_id=user_id,
                project_id=project_id,
                level=level,
                title=title,
                message=message,
                route=route,
                source_type=source_type,
                source_id=source_id,
                status="未读",
                read_at=None,
            )
        )
    elif note.status == "已归档":
        return
    else:
        note.level = level
        note.title = title
        note.message = message
        note.route = route
        note.updated_at = _now()


def ensure_workbench_state(
    db: Session,
    user: dict[str, Any],
    project_by_id: dict[str, Project],
    documents: Iterable[ProjectDocument],
    facts: Iterable[FactItem],
    chapters: Iterable[ReportChapter],
    issues: Iterable[QualityIssue],
    estimates: Iterable[InvestmentEstimate],
) -> None:
    """Materialise derived workbench events into persistent work/review/notification tables.

    The function is idempotent by source_type + source_id. Completed/cancelled user actions are not overwritten.
    """
    actor = user.get("id") or user.get("name") or "system"
    for document in documents:
        if document.parse_status != "已解析":
            _upsert_work_item(
                db,
                source_type="project_document",
                source_id=document.id,
                project_id=document.project_id,
                category="资料解析",
                title=f"解析《{document.name}》",
                detail=f"{document.category} · {document.version}",
                priority="P0" if document.parse_status == "需复核" else "P1",
                owner="资料管理员",
                route="/documents",
                created_by=actor,
            )

    for fact in facts:
        if fact.status in {"待确认", "有冲突"}:
            _upsert_work_item(
                db,
                source_type="fact_item",
                source_id=fact.id,
                project_id=fact.project_id,
                category="事实确认",
                title=f"{fact.name}：{fact.value}{fact.unit or ''}",
                detail=fact.source,
                priority="P0" if fact.status == "有冲突" else "P1",
                owner=fact.owner,
                route="/facts",
                created_by=actor,
            )

    for chapter in chapters:
        if chapter.status in {"未开始", "编制中"}:
            _upsert_work_item(
                db,
                source_type="report_chapter",
                source_id=chapter.id,
                project_id=chapter.project_id,
                category="章节编制",
                title=f"{chapter.chapter_no} {chapter.title}",
                detail=f"引用 {chapter.citation_count} 条 · 质量级别 {chapter.quality}",
                priority="P1" if chapter.quality in {"阻断", "严重"} else "P2",
                owner=chapter.owner,
                route="/report",
                created_by=actor,
            )
        if chapter.status == "待审核":
            _upsert_review_task(
                db,
                target_type="report_chapter",
                target_id=chapter.id,
                project_id=chapter.project_id,
                title=f"{chapter.chapter_no} {chapter.title}",
                description=f"当前引用 {chapter.citation_count} 条，质量级别 {chapter.quality}",
                priority="P0" if chapter.quality in {"阻断", "严重"} else "P1",
                submitter=chapter.owner,
                route="/report",
            )

    for issue in issues:
        if issue.status != "已关闭":
            _upsert_work_item(
                db,
                source_type="quality_issue",
                source_id=issue.id,
                project_id=issue.project_id,
                category="质量问题",
                title=issue.title,
                detail=f"{issue.severity} · {issue.type}",
                priority=SEVERITY_PRIORITY.get(issue.severity, "P2"),
                owner=issue.owner,
                route="/quality",
                created_by=actor,
            )
            if issue.severity in {"阻断", "严重"}:
                _upsert_notification(
                    db,
                    source_type="quality_issue",
                    source_id=issue.id,
                    project_id=issue.project_id,
                    level="danger",
                    title=f"{issue.severity}质量问题：{issue.title}",
                    message="正式发布前必须处理并复检关闭。",
                    route="/quality",
                )

    for estimate in estimates:
        if estimate.status == "calculated":
            project = project_by_id.get(estimate.project_id)
            _upsert_review_task(
                db,
                target_type="investment_estimate",
                target_id=estimate.id,
                project_id=estimate.project_id,
                title=f"{project.name if project else estimate.project_id}投资估算结果",
                description="测算已完成，待专业人员确认后用于正式成果。",
                priority="P1",
                submitter="投资测算引擎",
                route="/analysis",
            )


def map_work_item(item: WorkItem, project_by_id: dict[str, Project], users_by_id: dict[str, AppUser] | None = None) -> dict[str, Any]:
    project = project_by_id.get(item.project_id or "")
    assignee = users_by_id.get(item.assignee_id or "") if users_by_id else None
    return {
        "id": item.id,
        "category": item.category,
        "title": item.title,
        "projectId": item.project_id,
        "projectName": project.name if project else "未关联项目",
        "owner": item.owner,
        "assigneeId": item.assignee_id,
        "assigneeName": assignee.name if assignee else None,
        "priority": item.priority,
        "status": item.status,
        "route": item.route,
        "detail": item.detail,
        "dueAt": item.due_at.isoformat() if item.due_at else None,
        "sourceType": item.source_type,
        "sourceId": item.source_id,
        "persistent": True,
    }


def map_review_task(task: ReviewTask, project_by_id: dict[str, Project], users_by_id: dict[str, AppUser] | None = None) -> dict[str, Any]:
    project = project_by_id.get(task.project_id or "")
    reviewer = users_by_id.get(task.reviewer_id or "") if users_by_id else None
    return {
        "id": task.id,
        "type": task.target_type,
        "title": task.title,
        "projectId": task.project_id,
        "projectName": project.name if project else "未关联项目",
        "submitter": task.submitter,
        "reviewerId": task.reviewer_id,
        "reviewerName": reviewer.name if reviewer else None,
        "priority": task.priority,
        "status": task.status,
        "route": task.route,
        "description": task.description,
        "targetType": task.target_type,
        "targetId": task.target_id,
        "decision": task.decision,
        "comment": task.comment,
        "persistent": True,
    }


def map_notification(note: Notification) -> dict[str, Any]:
    return {
        "id": note.id,
        "level": note.level,
        "title": note.title,
        "message": note.message,
        "route": note.route,
        "status": note.status,
        "projectId": note.project_id,
        "sourceType": note.source_type,
        "sourceId": note.source_id,
        "createdAt": note.created_at.isoformat() if note.created_at else None,
    }



def add_workbench_event(
    db: Session,
    *,
    project_id: str | None,
    target_type: str,
    target_id: str,
    action: str,
    actor: dict[str, Any],
    comment: str | None = None,
    payload: dict[str, Any] | None = None,
) -> WorkbenchEvent:
    event = WorkbenchEvent(
        id=_new_id("WE"),
        project_id=project_id,
        target_type=target_type,
        target_id=target_id,
        action=action,
        actor_id=actor.get("id"),
        actor_name=actor.get("name") or actor.get("id") or "system",
        comment=comment,
        payload=payload or {},
    )
    db.add(event)
    return event


def add_task_event(
    db: Session,
    *,
    project_id: str | None,
    task_kind: str,
    task_id: str,
    status: str,
    stage: str,
    message: str,
    actor: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> TaskEvent:
    event = TaskEvent(
        id=_new_id("TE"),
        project_id=project_id,
        task_kind=task_kind,
        task_id=task_id,
        status=status,
        stage=stage,
        message=message,
        actor_id=actor.get("id") if actor else None,
        actor_name=actor.get("name") if actor else None,
        payload=payload or {},
    )
    db.add(event)
    return event


def map_workbench_event(event: WorkbenchEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "projectId": event.project_id,
        "targetType": event.target_type,
        "targetId": event.target_id,
        "action": event.action,
        "actorId": event.actor_id,
        "actorName": event.actor_name,
        "comment": event.comment,
        "payload": event.payload or {},
        "createdAt": event.created_at.isoformat() if event.created_at else None,
    }


def map_task_event(event: TaskEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "projectId": event.project_id,
        "taskKind": event.task_kind,
        "taskId": event.task_id,
        "status": event.status,
        "stage": event.stage,
        "message": event.message,
        "actorId": event.actor_id,
        "actorName": event.actor_name,
        "payload": event.payload or {},
        "createdAt": event.created_at.isoformat() if event.created_at else None,
    }
