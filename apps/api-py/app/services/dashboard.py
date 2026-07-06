from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AppUser,
    Artifact,
    AuditLog,
    FactItem,
    InvestmentEstimate,
    Notification,
    ParseJob,
    Project,
    ProjectDocument,
    QualityCheckJob,
    QualityIssue,
    ReportChapter,
    ReviewTask,
    TaskEvent,
    WorkbenchEvent,
    WorkItem,
)
from app.services.workbench import (
    ACTIVE_REVIEW_STATUSES,
    ACTIVE_WORK_STATUSES,
    add_task_event,
    apply_project_visibility,
    ensure_workbench_state,
    is_management_role,
    map_notification,
    ensure_sla_notifications,
    map_review_task,
    map_task_event,
    map_work_item,
    map_workbench_event,
    visible_project_ids,
)


PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def _percentage(done: int, total: int) -> int:
    return round(done * 100 / total) if total else 0


def _role_mode(role: str) -> str:
    return "management" if is_management_role(role) else "personal"


def _normalise_task_status(status: str) -> str:
    mapping = {
        "queued": "排队中",
        "pending": "排队中",
        "running": "运行中",
        "started": "运行中",
        "completed": "已完成",
        "success": "已完成",
        "failed": "失败",
        "error": "失败",
        "cancelled": "已取消",
        "revoked": "已取消",
        "生成中": "运行中",
        "已生成": "已完成",
        "受阻": "失败",
        "可生成": "待启动",
    }
    return mapping.get(status, status)


def _task_progress(status: str) -> int:
    if status in {"completed", "success", "已生成"}:
        return 100
    if status in {"failed", "error", "受阻", "cancelled", "revoked"}:
        return 0
    if status in {"running", "started", "生成中"}:
        return 60
    if status in {"queued", "pending"}:
        return 15
    return 5


def _is_stuck(status: str, updated_at: datetime | None, threshold_minutes: int = 30) -> bool:
    if status not in {"queued", "pending", "running", "started", "生成中"} or not updated_at:
        return False
    now = datetime.now(updated_at.tzinfo or timezone.utc)
    return (now - updated_at).total_seconds() > threshold_minutes * 60


def _has_task_event(db: Session, task_kind: str, task_id: str, stage: str) -> bool:
    fake_rows = getattr(db, "rows_by_model", None)
    if fake_rows is not None:
        return any(
            item.task_kind == task_kind and item.task_id == task_id and item.stage == stage
            for item in fake_rows.get(TaskEvent, [])
        )
    return bool(
        db.scalar(
            select(TaskEvent).where(
                TaskEvent.task_kind == task_kind,
                TaskEvent.task_id == task_id,
                TaskEvent.stage == stage,
            )
        )
    )


def _record_stuck_task_events(db: Session, tasks: list[dict[str, Any]], user: dict[str, Any]) -> None:
    for task in tasks:
        if not task.get("stuck"):
            continue
        if _has_task_event(db, task["taskKind"], task["id"], "stuck_detected"):
            continue
        add_task_event(
            db,
            project_id=task.get("projectId"),
            task_kind=task["taskKind"],
            task_id=task["id"],
            status=task.get("rawStatus") or task.get("status") or "stuck",
            stage="stuck_detected",
            message="工作台检测到任务长时间无进度，建议取消或重试。",
            actor=user,
            payload={"updatedAt": task.get("updatedAt"), "taskName": task.get("name")},
        )




def _minutes_since(value: datetime | str | None) -> int | None:
    if not isinstance(value, datetime):
        return None
    now = datetime.now(value.tzinfo or timezone.utc)
    return max(0, round((now - value).total_seconds() / 60))


def _task_heartbeat(updated_at: datetime | str | None, stuck: bool) -> dict[str, Any]:
    minutes = _minutes_since(updated_at)
    if minutes is None:
        return {"level": "unknown", "message": "无更新时间", "minutesSinceUpdate": None}
    if stuck:
        return {"level": "danger", "message": f"{minutes} 分钟未更新", "minutesSinceUpdate": minutes}
    if minutes > 20:
        return {"level": "warning", "message": f"{minutes} 分钟未更新", "minutesSinceUpdate": minutes}
    return {"level": "normal", "message": f"{minutes} 分钟内有更新", "minutesSinceUpdate": minutes}


def _card_health(key: str, label: str, total: int, alerts: int = 0, status: str | None = None) -> dict[str, Any]:
    resolved_status = status or ("danger" if alerts else "normal")
    messages = {
        "normal": "运行正常",
        "warning": "需要关注",
        "danger": "存在阻断或逾期",
        "degraded": "部分数据不可用",
        "empty": "暂无数据",
    }
    if total == 0 and not alerts and not status:
        resolved_status = "empty"
    return {
        "key": key,
        "label": label,
        "status": resolved_status,
        "count": total,
        "alerts": alerts,
        "message": messages.get(resolved_status, resolved_status),
    }


def _sla_summary(work_items: list[dict[str, Any]], review_queue: list[dict[str, Any]]) -> dict[str, Any]:
    rows = work_items + review_queue
    overdue = [item for item in rows if item.get("dueStatus") == "overdue"]
    due_soon = [item for item in rows if item.get("dueStatus") == "due_soon"]
    return {
        "overdue": len(overdue),
        "dueSoon": len(due_soon),
        "normal": sum(1 for item in rows if item.get("dueStatus") == "normal"),
        "total": len(rows),
        "level": "danger" if overdue else "warning" if due_soon else "normal",
        "message": f"{len(overdue)} 个逾期，{len(due_soon)} 个24小时内到期",
    }


def _iso(value: datetime | str | None) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _activity_label(action: str) -> str:
    labels = {
        "create_project": "新建项目",
        "create_document": "登记资料",
        "upload_document": "上传资料",
        "queue_document_parse": "提交资料解析",
        "update_fact": "更新事实",
        "generate_chapter_draft": "生成章节初稿",
        "update_chapter": "更新章节",
        "update_quality_issue": "处理质量问题",
        "run_quality_check": "执行质量检查",
        "queue_artifact_export": "提交成果导出",
        "claim_work_item": "领取工作项",
        "complete_work_item": "完成工作项",
        "transfer_work_item": "转交工作项",
        "approve_review_task": "通过审核任务",
        "reject_review_task": "退回审核任务",
        "read_notification": "已读通知",
        "cancel_background_task": "取消后台任务",
        "retry_background_task": "重试后台任务",
    }
    return labels.get(action, action.replace("_", " "))


def build_dashboard(db: Session, user: dict[str, Any], project_id: str | None = None) -> dict[str, Any]:
    all_projects_raw = db.scalars(select(Project).order_by(Project.updated_at.desc(), Project.id)).all()
    visibility = visible_project_ids(db, user)
    all_projects = apply_project_visibility(all_projects_raw, visibility)

    if project_id:
        scoped_projects = [project for project in all_projects if project.id == project_id]
        if not scoped_projects and all_projects:
            scoped_projects = all_projects[:1]
    else:
        scoped_projects = all_projects

    project_ids = [project.id for project in scoped_projects]
    project_by_id = {project.id: project for project in all_projects}

    if project_ids:
        documents = db.scalars(
            select(ProjectDocument)
            .where(ProjectDocument.project_id.in_(project_ids))
            .order_by(ProjectDocument.created_at.desc(), ProjectDocument.id)
        ).all()
        facts = db.scalars(select(FactItem).where(FactItem.project_id.in_(project_ids)).order_by(FactItem.id)).all()
        chapters = db.scalars(
            select(ReportChapter)
            .where(ReportChapter.project_id.in_(project_ids))
            .order_by(ReportChapter.chapter_no)
        ).all()
        issues = db.scalars(select(QualityIssue).where(QualityIssue.project_id.in_(project_ids)).order_by(QualityIssue.id)).all()
        artifacts = db.scalars(select(Artifact).where(Artifact.project_id.in_(project_ids)).order_by(Artifact.id)).all()
        estimates = db.scalars(
            select(InvestmentEstimate)
            .where(InvestmentEstimate.project_id.in_(project_ids))
            .order_by(InvestmentEstimate.created_at.desc())
        ).all()
    else:
        documents, facts, chapters, issues, artifacts, estimates = [], [], [], [], [], []

    ensure_workbench_state(db, user, project_by_id, documents, facts, chapters, issues, estimates)
    db.commit()

    users = db.scalars(select(AppUser).order_by(AppUser.id)).all()
    users_by_id = {user_row.id: user_row for user_row in users}

    work_stmt = select(WorkItem).where(WorkItem.status.in_(ACTIVE_WORK_STATUSES))
    review_stmt = select(ReviewTask).where(ReviewTask.status.in_(ACTIVE_REVIEW_STATUSES))
    notification_stmt = select(Notification).where(Notification.status == "未读")
    if project_ids:
        work_stmt = work_stmt.where(WorkItem.project_id.in_(project_ids))
        review_stmt = review_stmt.where(ReviewTask.project_id.in_(project_ids))
        notification_stmt = notification_stmt.where(Notification.project_id.in_(project_ids) | (Notification.project_id.is_(None)))
    elif visibility is not None:
        work_stmt = work_stmt.where(WorkItem.project_id.in_(project_ids))
        review_stmt = review_stmt.where(ReviewTask.project_id.in_(project_ids))
        notification_stmt = notification_stmt.where(Notification.project_id.in_(project_ids))

    if not is_management_role(user.get("role")):
        uid = user.get("id")
        # Personal view: show unassigned, assigned-to-me, or items on visible projects.
        work_stmt = work_stmt.where((WorkItem.assignee_id.is_(None)) | (WorkItem.assignee_id == uid))
        review_stmt = review_stmt.where((ReviewTask.reviewer_id.is_(None)) | (ReviewTask.reviewer_id == uid))
        notification_stmt = notification_stmt.where((Notification.user_id.is_(None)) | (Notification.user_id == uid))

    work_items_rows = db.scalars(work_stmt.order_by(WorkItem.priority, WorkItem.updated_at.desc()).limit(50)).all()
    review_rows = db.scalars(review_stmt.order_by(ReviewTask.priority, ReviewTask.updated_at.desc()).limit(30)).all()
    ensure_sla_notifications(db, work_items_rows, review_rows)
    db.commit()
    note_rows = db.scalars(notification_stmt.order_by(Notification.created_at.desc()).limit(20)).all()

    work_items = [map_work_item(item, project_by_id, users_by_id, user) for item in work_items_rows]
    work_items.sort(key=lambda item: (PRIORITY_ORDER.get(item["priority"], 9), item["category"], item["title"]))
    review_queue = [map_review_task(item, project_by_id, users_by_id, user) for item in review_rows]
    review_queue.sort(key=lambda item: PRIORITY_ORDER.get(item["priority"], 9))

    document_by_id = {document.id: document for document in documents}

    parse_jobs = []
    if document_by_id:
        parse_jobs = db.scalars(
            select(ParseJob)
            .where(ParseJob.document_id.in_(list(document_by_id)))
            .order_by(ParseJob.created_at.desc())
            .limit(30)
        ).all()

    quality_jobs = []
    if project_ids:
        quality_jobs = db.scalars(
            select(QualityCheckJob)
            .where(QualityCheckJob.project_id.in_(project_ids))
            .order_by(QualityCheckJob.created_at.desc())
            .limit(30)
        ).all()

    tasks: list[dict[str, Any]] = []
    for job in parse_jobs:
        document = document_by_id.get(job.document_id or "")
        if not document:
            continue
        project = project_by_id.get(document.project_id)
        updated_at = job.updated_at or job.created_at
        tasks.append(
            {
                "id": job.id,
                "taskKind": "parse",
                "type": "资料解析",
                "name": document.name,
                "projectId": document.project_id,
                "projectName": project.name if project else "未知项目",
                "status": _normalise_task_status(job.status),
                "rawStatus": job.status,
                "message": job.message,
                "progress": _task_progress(job.status),
                "updatedAt": _iso(updated_at),
                "route": "/documents",
                "stuck": _is_stuck(job.status, updated_at),
                "heartbeat": _task_heartbeat(updated_at, _is_stuck(job.status, updated_at)),
                "stuckMinutes": _minutes_since(updated_at) if _is_stuck(job.status, updated_at) else None,
                "canCancel": job.status in {"queued", "pending", "running", "started"},
                "canRetry": job.status in {"failed", "error", "cancelled", "revoked"},
            }
        )
    for job in quality_jobs:
        project = project_by_id.get(job.project_id or "")
        updated_at = job.updated_at or job.created_at
        tasks.append(
            {
                "id": job.id,
                "taskKind": "quality",
                "type": "质量检查",
                "name": "项目质量检查",
                "projectId": job.project_id,
                "projectName": project.name if project else "全部项目",
                "status": _normalise_task_status(job.status),
                "rawStatus": job.status,
                "message": job.message,
                "progress": _task_progress(job.status),
                "updatedAt": _iso(updated_at),
                "route": "/quality",
                "stuck": _is_stuck(job.status, updated_at),
                "heartbeat": _task_heartbeat(updated_at, _is_stuck(job.status, updated_at)),
                "stuckMinutes": _minutes_since(updated_at) if _is_stuck(job.status, updated_at) else None,
                "canCancel": job.status in {"queued", "pending", "running", "started"},
                "canRetry": job.status in {"failed", "error", "cancelled", "revoked"},
            }
        )
    for artifact in artifacts:
        if artifact.status not in {"生成中", "受阻"}:
            continue
        tasks.append(
            {
                "id": artifact.id,
                "taskKind": "artifact",
                "type": "成果导出",
                "name": artifact.name,
                "projectId": artifact.project_id,
                "projectName": project_by_id[artifact.project_id].name,
                "status": _normalise_task_status(artifact.status),
                "rawStatus": artifact.status,
                "message": "成果正在生成" if artifact.status == "生成中" else "成果生成受阻，请处理质量问题后重试",
                "progress": _task_progress(artifact.status),
                "updatedAt": artifact.updated_at,
                "route": "/artifacts",
                "stuck": False,
                "heartbeat": _task_heartbeat(None, False),
                "stuckMinutes": None,
                "canCancel": artifact.status == "生成中",
                "canRetry": artifact.status == "受阻",
            }
        )
    tasks.sort(key=lambda item: (0 if item["status"] in {"失败", "运行中", "排队中"} else 1, item.get("updatedAt") or ""))
    tasks = tasks[:16]

    unresolved_issues = [issue for issue in issues if issue.status != "已关闭"]
    blockers = [issue for issue in unresolved_issues if issue.severity in {"阻断", "严重"}]
    generated_artifacts = [artifact for artifact in artifacts if artifact.status == "已生成"]
    running_tasks = [task for task in tasks if task["status"] in {"排队中", "运行中"}]
    failed_tasks = [task for task in tasks if task["status"] == "失败"]
    stuck_tasks = [task for task in tasks if task.get("stuck")]
    if stuck_tasks:
        _record_stuck_task_events(db, stuck_tasks, user)
        db.commit()

    sla_summary = _sla_summary(work_items, review_queue)
    card_health = [
        _card_health("projects", "项目范围", len(scoped_projects)),
        _card_health("workItems", "待办事项", len(work_items), sla_summary["overdue"]),
        _card_health("reviewQueue", "审核队列", len(review_queue), sum(1 for item in review_queue if item.get("dueStatus") == "overdue")),
        _card_health("tasks", "异步任务", len(tasks), len(stuck_tasks) + len(failed_tasks)),
        _card_health("quality", "质量问题", len(unresolved_issues), len(blockers)),
        _card_health("notifications", "提醒通知", len(note_rows)),
    ]

    avg_project_progress = round(sum(project.progress for project in scoped_projects) / len(scoped_projects)) if scoped_projects else 0
    metrics = [
        {
            "key": "projectProgress",
            "label": "项目综合进度",
            "value": avg_project_progress,
            "unit": "%",
            "description": f"当前范围共 {len(scoped_projects)} 个项目",
            "tone": "primary",
            "route": "/projects",
        },
        {
            "key": "pendingWork",
            "label": "待办事项",
            "value": len(work_items),
            "unit": "项",
            "description": f"其中 P0 {sum(1 for item in work_items if item['priority'] == 'P0')} 项",
            "tone": "warning" if work_items else "success",
            "route": "/dashboard",
        },
        {
            "key": "pendingReview",
            "label": "待审核/确认",
            "value": len(review_queue),
            "unit": "项",
            "description": "章节、投资测算与专业复核",
            "tone": "warning" if review_queue else "success",
            "route": "/report",
        },
        {
            "key": "blockingIssues",
            "label": "严重及阻断问题",
            "value": len(blockers),
            "unit": "项",
            "description": "未关闭问题影响正式发布",
            "tone": "danger" if blockers else "success",
            "route": "/quality",
        },
        {
            "key": "runningTasks",
            "label": "运行中任务",
            "value": len(running_tasks),
            "unit": "个",
            "description": f"失败 {len(failed_tasks)} 个，疑似卡住 {len(stuck_tasks)} 个",
            "tone": "danger" if stuck_tasks or failed_tasks else "info" if running_tasks else "success",
            "route": "/dashboard",
        },
        {
            "key": "artifacts",
            "label": "已生成成果",
            "value": len(generated_artifacts),
            "unit": "份",
            "description": f"成果配置共 {len(artifacts)} 项",
            "tone": "primary",
            "route": "/artifacts",
        },
    ]

    workflow = [
        {
            "key": "documents",
            "name": "资料解析",
            "done": sum(1 for item in documents if item.parse_status == "已解析"),
            "total": len(documents),
            "percentage": _percentage(sum(1 for item in documents if item.parse_status == "已解析"), len(documents)),
            "route": "/documents",
        },
        {
            "key": "facts",
            "name": "事实确认",
            "done": sum(1 for item in facts if item.status in {"已确认", "已锁定"}),
            "total": len(facts),
            "percentage": _percentage(sum(1 for item in facts if item.status in {"已确认", "已锁定"}), len(facts)),
            "route": "/facts",
        },
        {
            "key": "chapters",
            "name": "章节审核",
            "done": sum(1 for item in chapters if item.status == "已审核"),
            "total": len(chapters),
            "percentage": _percentage(sum(1 for item in chapters if item.status == "已审核"), len(chapters)),
            "route": "/report",
        },
        {
            "key": "quality",
            "name": "质量问题关闭",
            "done": sum(1 for item in issues if item.status == "已关闭"),
            "total": len(issues),
            "percentage": _percentage(sum(1 for item in issues if item.status == "已关闭"), len(issues)),
            "route": "/quality",
        },
        {
            "key": "artifacts",
            "name": "成果生成",
            "done": len(generated_artifacts),
            "total": len(artifacts),
            "percentage": _percentage(len(generated_artifacts), len(artifacts)),
            "route": "/artifacts",
        },
    ]

    project_summaries = []
    for project in scoped_projects:
        project_documents = [item for item in documents if item.project_id == project.id]
        project_facts = [item for item in facts if item.project_id == project.id]
        project_chapters = [item for item in chapters if item.project_id == project.id]
        project_issues = [item for item in issues if item.project_id == project.id and item.status != "已关闭"]
        project_summaries.append(
            {
                "id": project.id,
                "name": project.name,
                "type": project.type,
                "phase": project.phase,
                "owner": project.owner,
                "location": project.location,
                "progress": project.progress,
                "risk": project.risk,
                "documents": f"{sum(1 for item in project_documents if item.parse_status == '已解析')}/{len(project_documents)}",
                "facts": f"{sum(1 for item in project_facts if item.status in {'已确认', '已锁定'})}/{len(project_facts)}",
                "chapters": f"{sum(1 for item in project_chapters if item.status == '已审核')}/{len(project_chapters)}",
                "openIssues": len(project_issues),
            }
        )

    notifications = [map_notification(item) for item in note_rows]
    overdue_work = [item for item in work_items if item.get("dueStatus") == "overdue"]
    due_soon_work = [item for item in work_items if item.get("dueStatus") == "due_soon"]
    overdue_review = [item for item in review_queue if item.get("dueStatus") == "overdue"]
    due_soon_review = [item for item in review_queue if item.get("dueStatus") == "due_soon"]
    if overdue_work or overdue_review:
        notifications.insert(
            0,
            {
                "id": "overdue-workbench-items",
                "level": "danger",
                "title": f"有 {len(overdue_work) + len(overdue_review)} 个工作台事项已逾期",
                "message": "请优先处理逾期待办和审核任务。",
                "route": "/dashboard",
                "status": "未读",
            },
        )
    elif due_soon_work or due_soon_review:
        notifications.insert(
            0,
            {
                "id": "due-soon-workbench-items",
                "level": "warning",
                "title": f"有 {len(due_soon_work) + len(due_soon_review)} 个事项即将到期",
                "message": "请在24小时内完成、转交或审核。",
                "route": "/dashboard",
                "status": "未读",
            },
        )
    if stuck_tasks:
        notifications.insert(
            0,
            {
                "id": "stuck-tasks",
                "level": "danger",
                "title": f"有 {len(stuck_tasks)} 个任务疑似卡住",
                "message": "请在异步任务中心取消或重试。",
                "route": "/dashboard",
                "status": "未读",
            },
        )
    if not notifications:
        notifications.append(
            {
                "id": "all-clear",
                "level": "success",
                "title": "当前没有高优先级提醒",
                "message": "项目流程运行正常，可继续推进下一阶段。",
                "route": "/dashboard",
                "status": "已读",
            }
        )

    event_stmt = select(WorkbenchEvent)
    task_event_stmt = select(TaskEvent)
    if project_ids:
        event_stmt = event_stmt.where(WorkbenchEvent.project_id.in_(project_ids) | (WorkbenchEvent.project_id.is_(None)))
        task_event_stmt = task_event_stmt.where(TaskEvent.project_id.in_(project_ids) | (TaskEvent.project_id.is_(None)))
    elif visibility is not None:
        event_stmt = event_stmt.where(WorkbenchEvent.project_id.in_(project_ids))
        task_event_stmt = task_event_stmt.where(TaskEvent.project_id.in_(project_ids))
    latest_events = [map_workbench_event(item) for item in db.scalars(event_stmt.order_by(WorkbenchEvent.created_at.desc()).limit(20)).all()]
    task_events = [map_task_event(item) for item in db.scalars(task_event_stmt.order_by(TaskEvent.created_at.desc()).limit(30)).all()]

    activity_project_filter = list(project_by_id)
    activity_query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(12)
    recent_logs = db.scalars(activity_query).all()
    recent_activities = [
        {
            "id": str(log.id),
            "actor": log.actor,
            "action": _activity_label(log.action),
            "entityType": log.entity_type,
            "entityId": log.entity_id,
            "createdAt": log.created_at.isoformat(),
            "detail": log.detail or {},
        }
        for log in recent_logs
    ]

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "scope": "project" if project_id else "all",
        "roleMode": _role_mode(user.get("role", "")),
        "user": user,
        "metrics": metrics,
        "workflow": workflow,
        "projects": project_summaries,
        "workItems": work_items[:20],
        "reviewQueue": review_queue[:12],
        "tasks": tasks,
        "notifications": notifications[:12],
        "slaSummary": sla_summary,
        "cardHealth": card_health,
        "latestEvents": latest_events,
        "taskEvents": task_events,
        "recentActivities": recent_activities,
        "quickActions": [
            {"key": "upload", "label": "上传项目资料", "description": "补充资料并进入解析", "route": "/documents"},
            {"key": "facts", "label": "处理事实口径", "description": "确认或解决冲突事实", "route": "/facts"},
            {"key": "chapter", "label": "继续章节编制", "description": "生成初稿并完善引用", "route": "/report"},
            {"key": "quality", "label": "执行质量检查", "description": "检查发布门禁与一致性", "route": "/quality"},
        ],
        "capabilities": {
            "persistentWorkItems": True,
            "persistentReviewTasks": True,
            "persistentNotifications": True,
            "taskCancelRetry": True,
            "stuckDetection": True,
            "projectMemberFilter": True,
            "workItemComments": True,
            "reviewCountersign": True,
            "notificationBatchRead": True,
            "taskStageEvents": True,
            "rowActionPermissions": True,
            "workbenchSlaHints": True,
            "stuckTaskAuditEvents": True,
            "slaNotificationMaterialised": True,
            "taskHeartbeat": True,
            "cardHealth": True,
        },
    }
