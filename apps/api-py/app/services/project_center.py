from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    AppUser,
    Artifact,
    AuditLog,
    FactItem,
    Project,
    ProjectDocument,
    ProjectMember,
    ProjectMilestone,
    QualityIssue,
    ReportChapter,
    ReportTemplate,
)
from app.services.workbench import assert_project_visible, is_management_role, visible_project_ids

PROJECT_STATUSES = ["建档中", "进行中", "已关闭", "已归档"]
CONFIDENTIALITY_LEVELS = ["公开", "内部", "秘密", "机密"]
DEFAULT_MILESTONES = [
    ("资料清点", "资料负责人", 1),
    ("事实确认", "咨询负责人", 2),
    ("章节编制", "报告负责人", 3),
    ("质量审核", "审核负责人", 4),
    ("成果归档", "项目负责人", 5),
]


def new_id(prefix: str) -> str:
    return f"{prefix}-{int(time.time() * 1000)}"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def current_day() -> str:
    return now_utc().date().isoformat()


def project_code(project: Project) -> str:
    return getattr(project, "code", None) or project.id


def project_status(project: Project) -> str:
    return getattr(project, "status", None) or "进行中"


def project_confidentiality(project: Project) -> str:
    return getattr(project, "confidentiality", None) or "内部"


def _rows(db: Session, model: type[Any]) -> list[Any] | None:
    fake_rows = getattr(db, "rows_by_model", None)
    if fake_rows is None:
        return None
    return list(fake_rows.get(model, []))


def _visible_projects(db: Session, user: dict[str, Any]) -> list[Project]:
    fake = _rows(db, Project)
    rows = fake if fake is not None else db.scalars(select(Project).order_by(Project.created_at.desc(), Project.id)).all()
    visible_ids = visible_project_ids(db, user)
    if visible_ids is None:
        return rows
    return [row for row in rows if row.id in visible_ids]


def _filter_project_rows(db: Session, model: type[Any], project_id: str) -> list[Any]:
    fake = _rows(db, model)
    if fake is not None:
        return [row for row in fake if getattr(row, "project_id", None) == project_id]
    return db.scalars(select(model).where(model.project_id == project_id)).all()


def _map_user(user: AppUser | None) -> dict[str, Any] | None:
    if not user:
        return None
    return {"id": user.id, "name": user.name, "role": user.role, "department": user.department, "status": user.status, "email": user.email}


def _user_by_id(db: Session, user_id: str | None) -> AppUser | None:
    if not user_id:
        return None
    fake = _rows(db, AppUser)
    if fake is not None:
        return next((row for row in fake if row.id == user_id), None)
    return db.get(AppUser, user_id)


def map_project_member(db: Session, row: ProjectMember) -> dict[str, Any]:
    user = _user_by_id(db, row.user_id)
    return {
        "projectId": row.project_id,
        "userId": row.user_id,
        "name": user.name if user else row.user_id,
        "email": user.email if user else None,
        "department": user.department if user else None,
        "userStatus": user.status if user else None,
        "role": row.role,
    }


def map_milestone(row: ProjectMilestone) -> dict[str, Any]:
    return {
        "id": row.id,
        "projectId": row.project_id,
        "name": row.name,
        "owner": row.owner,
        "status": row.status,
        "dueAt": row.due_at,
        "completedAt": row.completed_at.isoformat() if row.completed_at else None,
        "sortOrder": row.sort_order,
    }


def map_project_summary(db: Session, project: Project) -> dict[str, Any]:
    documents = _filter_project_rows(db, ProjectDocument, project.id)
    facts = _filter_project_rows(db, FactItem, project.id)
    chapters = _filter_project_rows(db, ReportChapter, project.id)
    issues = _filter_project_rows(db, QualityIssue, project.id)
    artifacts = _filter_project_rows(db, Artifact, project.id)
    milestones = _filter_project_rows(db, ProjectMilestone, project.id)
    members = _filter_project_rows(db, ProjectMember, project.id)
    open_issues = [item for item in issues if item.status != "已关闭"]
    blockers = [item for item in open_issues if item.severity == "阻断"]
    done_milestones = len([item for item in milestones if item.status == "已完成"])
    return {
        "id": project.id,
        "code": project_code(project),
        "name": project.name,
        "type": project.type,
        "location": project.location,
        "phase": project.phase,
        "owner": project.owner,
        "status": project_status(project),
        "confidentiality": project_confidentiality(project),
        "templateId": getattr(project, "template_id", None),
        "templateVersion": getattr(project, "template_version", None),
        "plannedStart": getattr(project, "planned_start", None),
        "plannedEnd": getattr(project, "planned_end", None),
        "description": getattr(project, "description", None),
        "progress": project.progress,
        "risk": project.risk,
        "createdAt": project.created_at.isoformat() if getattr(project, "created_at", None) else None,
        "updatedAt": project.updated_at.isoformat() if getattr(project, "updated_at", None) else None,
        "archivedAt": project.archived_at.isoformat() if getattr(project, "archived_at", None) else None,
        "stats": {
            "documents": len(documents),
            "parsedDocuments": len([item for item in documents if item.parse_status == "已解析"]),
            "facts": len(facts),
            "confirmedFacts": len([item for item in facts if item.status in {"已确认", "已锁定"}]),
            "chapters": len(chapters),
            "approvedChapters": len([item for item in chapters if item.status == "已审核"]),
            "openIssues": len(open_issues),
            "blockingIssues": len(blockers),
            "artifacts": len(artifacts),
            "generatedArtifacts": len([item for item in artifacts if item.status == "已生成"]),
            "members": len(members),
            "milestones": len(milestones),
            "completedMilestones": done_milestones,
        },
        "initialization": {
            "hasMembers": len(members) > 0,
            "hasMilestones": len(milestones) > 0,
            "hasTemplate": bool(getattr(project, "template_id", None) or getattr(project, "template_version", None)),
            "hasDocuments": len(documents) > 0,
            "ready": len(members) > 0 and len(milestones) > 0 and bool(getattr(project, "template_version", None)),
        },
    }


def map_project_profile(db: Session, project: Project, user: dict[str, Any]) -> dict[str, Any]:
    members = _filter_project_rows(db, ProjectMember, project.id)
    milestones = _filter_project_rows(db, ProjectMilestone, project.id)
    summary = map_project_summary(db, project)
    status = project_status(project)
    can_manage = is_management_role(user.get("role")) or any(row.user_id == user.get("id") and row.role in {"项目负责人", "项目管理员"} for row in members)
    return {
        **summary,
        "members": [map_project_member(db, row) for row in sorted(members, key=lambda item: (item.role, item.user_id))],
        "milestones": [map_milestone(row) for row in sorted(milestones, key=lambda item: (item.sort_order, item.id))],
        "actions": {
            "canEdit": can_manage and status not in {"已归档"},
            "canClose": can_manage and status in {"建档中", "进行中"},
            "canArchive": can_manage and status == "已关闭",
            "canReopen": can_manage and status in {"已关闭", "已归档"},
            "canCopy": can_manage,
        },
    }


def build_project_center(db: Session, user: dict[str, Any]) -> dict[str, Any]:
    projects = _visible_projects(db, user)
    summaries = [map_project_summary(db, project) for project in projects]
    active = [item for item in summaries if item["status"] in {"建档中", "进行中"}]
    risk_items = [item for item in summaries if item["risk"] in {"阻断", "严重"}]
    archived = [item for item in summaries if item["status"] == "已归档"]
    templates = _rows(db, ReportTemplate)
    if templates is None:
        templates = db.scalars(select(ReportTemplate).order_by(ReportTemplate.id)).all()
    users = _rows(db, AppUser)
    if users is None:
        users = db.scalars(select(AppUser).order_by(AppUser.id)).all()
    return {
        "generatedAt": now_utc().isoformat(),
        "metrics": [
            {"key": "total", "label": "项目总数", "value": len(summaries), "tone": "primary"},
            {"key": "active", "label": "进行中", "value": len(active), "tone": "success"},
            {"key": "risk", "label": "高风险", "value": len(risk_items), "tone": "danger" if risk_items else "info"},
            {"key": "archived", "label": "已归档", "value": len(archived), "tone": "info"},
        ],
        "projects": summaries,
        "templates": [
            {"id": row.id, "name": row.name, "reportType": row.report_type, "version": row.version, "status": row.status}
            for row in templates
            if row.status != "已停用"
        ],
        "users": [_map_user(row) for row in users if row.status == "启用"],
        "statuses": PROJECT_STATUSES,
        "confidentialityLevels": CONFIDENTIALITY_LEVELS,
        "capabilities": {
            "projectWizard": True,
            "projectProfile": True,
            "memberManagement": True,
            "milestoneManagement": True,
            "templateBinding": True,
            "confidentialitySettings": True,
            "statusFlow": True,
            "projectCopy": True,
            "uniqueProjectCode": True,
        },
    }


def generate_project_code(db: Session, project_type: str | None = None) -> str:
    prefix = "ZJ"
    year = now_utc().strftime("%Y")
    fake = _rows(db, Project)
    existing_codes = {project_code(row) for row in fake} if fake is not None else set(db.scalars(select(Project.code)).all())
    base = f"{prefix}-{year}"
    seq = len([code for code in existing_codes if code and code.startswith(base)]) + 1
    code = f"{base}-{seq:04d}"
    while code in existing_codes:
        seq += 1
        code = f"{base}-{seq:04d}"
    return code


def apply_project_defaults(project: Project, template: ReportTemplate | None = None) -> None:
    project.code = project.code or project.id
    project.status = project.status or "建档中"
    project.confidentiality = project.confidentiality or "内部"
    if template:
        project.template_id = template.id
        project.template_version = template.version
    project.updated_at = now_utc()


def ensure_project_member(db: Session, project_id: str, user_id: str, role: str) -> ProjectMember:
    existing = db.get(ProjectMember, {"project_id": project_id, "user_id": user_id}) if not getattr(db, "rows_by_model", None) else None
    if existing:
        existing.role = role
        return existing
    fake = _rows(db, ProjectMember)
    if fake is not None:
        existing = next((row for row in fake if row.project_id == project_id and row.user_id == user_id), None)
        if existing:
            existing.role = role
            return existing
    member = ProjectMember(project_id=project_id, user_id=user_id, role=role)
    db.add(member)
    return member


def add_default_milestones(db: Session, project: Project) -> list[ProjectMilestone]:
    existing = _filter_project_rows(db, ProjectMilestone, project.id)
    if existing:
        return existing
    milestones = []
    for name, owner, order in DEFAULT_MILESTONES:
        row = ProjectMilestone(id=f"PM-{project.id}-{order}", project_id=project.id, name=name, owner=owner, status="未开始", due_at=None, sort_order=order)
        db.add(row)
        milestones.append(row)
    return milestones


def can_change_status(project: Project, next_status: str) -> bool:
    status = project_status(project)
    allowed = {
        "建档中": {"进行中", "已关闭"},
        "进行中": {"已关闭"},
        "已关闭": {"进行中", "已归档"},
        "已归档": {"进行中"},
    }
    return next_status == status or next_status in allowed.get(status, set())
