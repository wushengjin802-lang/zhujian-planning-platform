from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Artifact,
    AuditLog,
    FactItem,
    InvestmentEstimate,
    ParseJob,
    Project,
    ProjectDocument,
    QualityCheckJob,
    QualityIssue,
    ReportChapter,
)


PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
SEVERITY_PRIORITY = {"阻断": "P0", "严重": "P0", "一般": "P1", "提示": "P2"}


def _percentage(done: int, total: int) -> int:
    return round(done * 100 / total) if total else 0


def _role_mode(role: str) -> str:
    management_keywords = ("管理员", "负责人", "领导", "审核", "经理")
    return "management" if any(keyword in role for keyword in management_keywords) else "personal"


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
    }
    return labels.get(action, action.replace("_", " "))


def build_dashboard(db: Session, user: dict[str, Any], project_id: str | None = None) -> dict[str, Any]:
    all_projects = db.scalars(select(Project).order_by(Project.updated_at.desc(), Project.id)).all()
    if project_id:
        scoped_projects = [project for project in all_projects if project.id == project_id]
        if not scoped_projects:
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
        facts = db.scalars(
            select(FactItem).where(FactItem.project_id.in_(project_ids)).order_by(FactItem.id)
        ).all()
        chapters = db.scalars(
            select(ReportChapter)
            .where(ReportChapter.project_id.in_(project_ids))
            .order_by(ReportChapter.chapter_no)
        ).all()
        issues = db.scalars(
            select(QualityIssue).where(QualityIssue.project_id.in_(project_ids)).order_by(QualityIssue.id)
        ).all()
        artifacts = db.scalars(
            select(Artifact).where(Artifact.project_id.in_(project_ids)).order_by(Artifact.id)
        ).all()
        estimates = db.scalars(
            select(InvestmentEstimate)
            .where(InvestmentEstimate.project_id.in_(project_ids))
            .order_by(InvestmentEstimate.created_at.desc())
        ).all()
    else:
        documents, facts, chapters, issues, artifacts, estimates = [], [], [], [], [], []

    document_by_id = {document.id: document for document in documents}

    parse_jobs = []
    if document_by_id:
        parse_jobs = db.scalars(
            select(ParseJob)
            .where(ParseJob.document_id.in_(list(document_by_id)))
            .order_by(ParseJob.created_at.desc())
            .limit(20)
        ).all()

    quality_jobs = []
    if project_ids:
        quality_jobs = db.scalars(
            select(QualityCheckJob)
            .where(QualityCheckJob.project_id.in_(project_ids))
            .order_by(QualityCheckJob.created_at.desc())
            .limit(20)
        ).all()

    unresolved_issues = [issue for issue in issues if issue.status != "已关闭"]
    blockers = [issue for issue in unresolved_issues if issue.severity in {"阻断", "严重"}]
    pending_reviews = [chapter for chapter in chapters if chapter.status == "待审核"]
    pending_estimate_reviews = [estimate for estimate in estimates if estimate.status == "calculated"]

    work_items: list[dict[str, Any]] = []
    for document in documents:
        if document.parse_status != "已解析":
            work_items.append(
                {
                    "id": f"document:{document.id}",
                    "category": "资料解析",
                    "title": f"解析《{document.name}》",
                    "projectId": document.project_id,
                    "projectName": project_by_id[document.project_id].name,
                    "owner": "资料管理员",
                    "priority": "P1" if document.parse_status != "需复核" else "P0",
                    "status": document.parse_status,
                    "route": "/documents",
                    "detail": f"{document.category} · {document.version}",
                }
            )

    for fact in facts:
        if fact.status in {"待确认", "有冲突"}:
            work_items.append(
                {
                    "id": f"fact:{fact.id}",
                    "category": "事实确认",
                    "title": f"{fact.name}：{fact.value}{fact.unit or ''}",
                    "projectId": fact.project_id,
                    "projectName": project_by_id[fact.project_id].name,
                    "owner": fact.owner,
                    "priority": "P0" if fact.status == "有冲突" else "P1",
                    "status": fact.status,
                    "route": "/facts",
                    "detail": fact.source,
                }
            )

    for chapter in chapters:
        if chapter.status in {"未开始", "编制中"}:
            work_items.append(
                {
                    "id": f"chapter:{chapter.id}",
                    "category": "章节编制",
                    "title": f"{chapter.chapter_no} {chapter.title}",
                    "projectId": chapter.project_id,
                    "projectName": project_by_id[chapter.project_id].name,
                    "owner": chapter.owner,
                    "priority": "P1" if chapter.quality in {"阻断", "严重"} else "P2",
                    "status": chapter.status,
                    "route": "/report",
                    "detail": f"引用 {chapter.citation_count} 条 · 质量级别 {chapter.quality}",
                }
            )

    for issue in unresolved_issues:
        work_items.append(
            {
                "id": f"issue:{issue.id}",
                "category": "质量问题",
                "title": issue.title,
                "projectId": issue.project_id,
                "projectName": project_by_id[issue.project_id].name,
                "owner": issue.owner,
                "priority": SEVERITY_PRIORITY.get(issue.severity, "P2"),
                "status": issue.status,
                "route": "/quality",
                "detail": f"{issue.severity} · {issue.type}",
            }
        )

    work_items.sort(key=lambda item: (PRIORITY_ORDER.get(item["priority"], 9), item["category"], item["title"]))

    review_queue: list[dict[str, Any]] = []
    for chapter in pending_reviews:
        review_queue.append(
            {
                "id": chapter.id,
                "type": "章节审核",
                "title": f"{chapter.chapter_no} {chapter.title}",
                "projectId": chapter.project_id,
                "projectName": project_by_id[chapter.project_id].name,
                "submitter": chapter.owner,
                "priority": "P0" if chapter.quality in {"阻断", "严重"} else "P1",
                "status": chapter.status,
                "route": "/report",
                "description": f"当前引用 {chapter.citation_count} 条，质量级别 {chapter.quality}",
            }
        )
    for estimate in pending_estimate_reviews:
        project = project_by_id[estimate.project_id]
        review_queue.append(
            {
                "id": estimate.id,
                "type": "投资测算确认",
                "title": f"{project.name}投资估算结果",
                "projectId": estimate.project_id,
                "projectName": project.name,
                "submitter": "投资测算引擎",
                "priority": "P1",
                "status": "待确认",
                "route": "/analysis",
                "description": "测算已完成，待专业人员确认后用于正式成果。",
            }
        )
    review_queue.sort(key=lambda item: PRIORITY_ORDER.get(item["priority"], 9))

    tasks: list[dict[str, Any]] = []
    for job in parse_jobs:
        document = document_by_id.get(job.document_id or "")
        if not document:
            continue
        project = project_by_id.get(document.project_id)
        tasks.append(
            {
                "id": job.id,
                "type": "资料解析",
                "name": document.name,
                "projectId": document.project_id,
                "projectName": project.name if project else "未知项目",
                "status": _normalise_task_status(job.status),
                "message": job.message,
                "progress": 100 if job.status == "completed" else 15 if job.status == "queued" else 55,
                "updatedAt": (job.updated_at or job.created_at).isoformat() if (job.updated_at or job.created_at) else None,
                "route": "/documents",
            }
        )
    for job in quality_jobs:
        project = project_by_id.get(job.project_id or "")
        tasks.append(
            {
                "id": job.id,
                "type": "质量检查",
                "name": "项目质量检查",
                "projectId": job.project_id,
                "projectName": project.name if project else "全部项目",
                "status": _normalise_task_status(job.status),
                "message": job.message,
                "progress": 100 if job.status == "completed" else 15 if job.status == "queued" else 55,
                "updatedAt": (job.updated_at or job.created_at).isoformat() if (job.updated_at or job.created_at) else None,
                "route": "/quality",
            }
        )
    for artifact in artifacts:
        if artifact.status not in {"生成中", "受阻"}:
            continue
        tasks.append(
            {
                "id": artifact.id,
                "type": "成果导出",
                "name": artifact.name,
                "projectId": artifact.project_id,
                "projectName": project_by_id[artifact.project_id].name,
                "status": _normalise_task_status(artifact.status),
                "message": "成果正在生成" if artifact.status == "生成中" else "成果生成受阻，请处理质量问题后重试",
                "progress": 60 if artifact.status == "生成中" else 0,
                "updatedAt": artifact.updated_at,
                "route": "/artifacts",
            }
        )
    tasks.sort(key=lambda item: (0 if item["status"] in {"失败", "运行中", "排队中"} else 1, item.get("updatedAt") or ""), reverse=False)
    tasks = tasks[:12]

    generated_artifacts = [artifact for artifact in artifacts if artifact.status == "已生成"]
    running_tasks = [task for task in tasks if task["status"] in {"排队中", "运行中"}]
    failed_tasks = [task for task in tasks if task["status"] == "失败"]

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
            "description": "章节与专业测算确认",
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
            "description": f"失败任务 {len(failed_tasks)} 个",
            "tone": "info" if running_tasks else "success",
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

    notifications: list[dict[str, Any]] = []
    if blockers:
        notifications.append(
            {
                "id": "blocking-issues",
                "level": "danger",
                "title": f"存在 {len(blockers)} 项严重或阻断问题",
                "message": "正式成果发布前必须处理并复检。",
                "route": "/quality",
            }
        )
    if pending_reviews:
        notifications.append(
            {
                "id": "pending-reviews",
                "level": "warning",
                "title": f"有 {len(pending_reviews)} 个章节等待审核",
                "message": "请专业审核人及时处理，避免影响项目里程碑。",
                "route": "/report",
            }
        )
    if failed_tasks:
        notifications.append(
            {
                "id": "failed-tasks",
                "level": "danger",
                "title": f"有 {len(failed_tasks)} 个后台任务失败",
                "message": "请查看任务信息，修复数据或服务后重新执行。",
                "route": "/dashboard",
            }
        )
    unparsed_count = sum(1 for document in documents if document.parse_status != "已解析")
    if unparsed_count:
        notifications.append(
            {
                "id": "unparsed-documents",
                "level": "info",
                "title": f"仍有 {unparsed_count} 份资料未完成解析",
                "message": "未解析资料不会进入事实抽取和章节引用。",
                "route": "/documents",
            }
        )
    if not notifications:
        notifications.append(
            {
                "id": "all-clear",
                "level": "success",
                "title": "当前没有高优先级提醒",
                "message": "项目流程运行正常，可继续推进下一阶段。",
                "route": "/dashboard",
            }
        )

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
        "notifications": notifications[:8],
        "recentActivities": recent_activities,
        "quickActions": [
            {"key": "upload", "label": "上传项目资料", "description": "补充资料并进入解析", "route": "/documents"},
            {"key": "facts", "label": "处理事实口径", "description": "确认或解决冲突事实", "route": "/facts"},
            {"key": "chapter", "label": "继续章节编制", "description": "生成初稿并完善引用", "route": "/report"},
            {"key": "quality", "label": "执行质量检查", "description": "检查发布门禁与一致性", "route": "/quality"},
        ],
    }
