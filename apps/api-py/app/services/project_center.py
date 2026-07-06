from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AppUser,
    Artifact,
    FactItem,
    Project,
    ProjectDocument,
    ProjectInitializationRecord,
    ProjectMaterialRequirement,
    ProjectMember,
    ProjectMilestone,
    QualityCheckJob,
    QualityIssue,
    ReportChapter,
    ReportTemplate,
)
from app.services.workbench import is_management_role, visible_project_ids

PROJECT_STATUSES = ["建档中", "进行中", "已关闭", "已归档"]
CONFIDENTIALITY_LEVELS = ["公开", "内部", "秘密", "机密"]
INITIALIZATION_PACKAGE_VERSION = "v2.1"
DEFAULT_MILESTONES = [
    ("资料清点", "资料负责人", 1),
    ("事实确认", "咨询负责人", 2),
    ("章节编制", "报告负责人", 3),
    ("质量审核", "审核负责人", 4),
    ("成果归档", "项目负责人", 5),
]
DEFAULT_MATERIAL_REQUIREMENTS = [
    ("立项资料", "项目立项批复或任务来源说明", True, 1),
    ("规划资料", "用地规划条件或规划设计要点", True, 2),
    ("基础资料", "项目区位与用地现状资料", True, 3),
    ("投资资料", "投资估算依据或类似项目指标", True, 4),
    ("需求资料", "建设单位需求说明或访谈纪要", True, 5),
    ("成果资料", "既有图纸、方案或相关成果", False, 6),
]
DEFAULT_FACT_FRAME = [
    ("项目基本信息", "建设地点", "", None, "待补充", "待确认"),
    ("项目基本信息", "建设内容", "", None, "待补充", "待确认"),
    ("建设规模", "用地面积", "", "㎡", "待补充", "待确认"),
    ("建设规模", "建筑面积", "", "㎡", "待补充", "待确认"),
    ("投资测算", "估算总投资", "", "万元", "待补充", "待确认"),
]
DEFAULT_CHAPTER_OUTLINE = [
    ("1", "项目概况", "报告负责人", 1),
    ("2", "建设必要性", "咨询负责人", 2),
    ("3", "建设条件与需求分析", "咨询负责人", 3),
    ("4", "建设内容与规模", "设计负责人", 4),
    ("5", "投资估算与资金筹措", "投资负责人", 5),
    ("6", "结论与建议", "项目负责人", 6),
]
DEFAULT_ARTIFACT_PLAN = [
    ("成果报告.docx", "Word"),
    ("事实与质量清单.xlsx", "Excel"),
    ("汇报简版.pptx", "PPT"),
    ("项目归档包.zip", "Archive"),
]
RUNNING_PARSE_STATUSES = {"queued", "running", "解析中", "待处理"}
RUNNING_QUALITY_STATUSES = {"queued", "running", "检查中", "待处理"}


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


def _existing_by_name(db: Session, model: type[Any], project_id: str, attr: str, value: str) -> Any | None:
    fake = _rows(db, model)
    if fake is not None:
        return next((row for row in fake if getattr(row, "project_id", None) == project_id and getattr(row, attr, None) == value), None)
    return db.scalars(select(model).where(model.project_id == project_id, getattr(model, attr) == value)).first()


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


def map_material_requirement(row: ProjectMaterialRequirement) -> dict[str, Any]:
    return {
        "id": row.id,
        "projectId": row.project_id,
        "category": row.category,
        "name": row.name,
        "required": bool(row.required),
        "status": row.status,
        "sourceType": row.source_type,
        "sourceId": row.source_id,
        "sortOrder": row.sort_order,
    }


def map_initialization_record(row: ProjectInitializationRecord) -> dict[str, Any]:
    return {
        "id": row.id,
        "projectId": row.project_id,
        "packageVersion": row.package_version,
        "status": row.status,
        "summary": row.summary or {},
        "createdBy": row.created_by,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def _initialization_records(db: Session, project_id: str) -> list[ProjectInitializationRecord]:
    rows = _filter_project_rows(db, ProjectInitializationRecord, project_id)
    return sorted(rows, key=lambda item: getattr(item, "created_at", None) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)


def _running_task_count(db: Session, project_id: str) -> int:
    parse_jobs = _rows(db, QualityCheckJob)
    # ParseJob does not have project_id directly, so the project relation is through documents.
    quality_jobs = _filter_project_rows(db, QualityCheckJob, project_id)
    running_quality = [row for row in quality_jobs if row.status in RUNNING_QUALITY_STATUSES]
    # Fallback for fake sessions where ParseJob may not be populated: document parse status covers most UI cases.
    documents = _filter_project_rows(db, ProjectDocument, project_id)
    running_docs = [row for row in documents if row.parse_status == "解析中"]
    return len(running_quality) + len(running_docs)


def _current_initialization_status(
    members: list[ProjectMember],
    milestones: list[ProjectMilestone],
    materials: list[ProjectMaterialRequirement],
    facts: list[FactItem],
    chapters: list[ReportChapter],
    artifacts: list[Artifact],
    project: Project,
) -> dict[str, Any]:
    required_materials = [item for item in materials if item.required]
    completed_required_materials = [item for item in required_materials if item.status in {"已上传", "已确认", "不适用"}]
    confirmed_facts = [item for item in facts if item.status in {"已确认", "已锁定"}]
    has_material_list = len(required_materials) > 0
    has_fact_frame = len(facts) > 0
    has_chapter_outline = len(chapters) > 0
    has_artifact_plan = len(artifacts) > 0
    checks = [
        {"key": "members", "label": "成员", "passed": len(members) > 0, "value": len(members), "required": 1},
        {"key": "milestones", "label": "里程碑", "passed": len(milestones) > 0, "value": len(milestones), "required": len(DEFAULT_MILESTONES)},
        {"key": "template", "label": "模板版本", "passed": bool(getattr(project, "template_version", None)), "value": getattr(project, "template_version", None), "required": "必填"},
        {"key": "materials", "label": "资料清单", "passed": has_material_list, "value": len(materials), "required": len(DEFAULT_MATERIAL_REQUIREMENTS)},
        {"key": "facts", "label": "事实框架", "passed": has_fact_frame, "value": len(facts), "required": len(DEFAULT_FACT_FRAME)},
        {"key": "chapters", "label": "章节目录", "passed": has_chapter_outline, "value": len(chapters), "required": len(DEFAULT_CHAPTER_OUTLINE)},
        {"key": "artifacts", "label": "成果项", "passed": has_artifact_plan, "value": len(artifacts), "required": len(DEFAULT_ARTIFACT_PLAN)},
    ]
    ready = all(item["passed"] for item in checks)
    upload_ready = has_material_list and len(completed_required_materials) >= max(1, len(required_materials))
    return {
        "hasMembers": len(members) > 0,
        "hasMilestones": len(milestones) > 0,
        "hasTemplate": bool(getattr(project, "template_id", None) or getattr(project, "template_version", None)),
        "hasMaterialList": has_material_list,
        "hasFactFrame": has_fact_frame,
        "hasChapterOutline": has_chapter_outline,
        "hasArtifactPlan": has_artifact_plan,
        "hasDocuments": False,  # set by caller for backward compatibility
        "ready": ready,
        "packageReady": ready,
        "materialUploadReady": upload_ready,
        "confirmedFacts": len(confirmed_facts),
        "requiredMaterials": len(required_materials),
        "completedRequiredMaterials": len(completed_required_materials),
        "checks": checks,
        "missing": [item for item in checks if not item["passed"]],
        "packageVersion": INITIALIZATION_PACKAGE_VERSION,
    }


def map_project_summary(db: Session, project: Project) -> dict[str, Any]:
    documents = _filter_project_rows(db, ProjectDocument, project.id)
    facts = _filter_project_rows(db, FactItem, project.id)
    chapters = _filter_project_rows(db, ReportChapter, project.id)
    issues = _filter_project_rows(db, QualityIssue, project.id)
    artifacts = _filter_project_rows(db, Artifact, project.id)
    milestones = _filter_project_rows(db, ProjectMilestone, project.id)
    members = _filter_project_rows(db, ProjectMember, project.id)
    materials = _filter_project_rows(db, ProjectMaterialRequirement, project.id)
    records = _initialization_records(db, project.id)
    open_issues = [item for item in issues if item.status != "已关闭"]
    blockers = [item for item in open_issues if item.severity == "阻断"]
    severe = [item for item in open_issues if item.severity == "严重"]
    done_milestones = len([item for item in milestones if item.status == "已完成"])
    initialization = _current_initialization_status(members, milestones, materials, facts, chapters, artifacts, project)
    initialization["hasDocuments"] = len(documents) > 0
    latest_record = map_initialization_record(records[0]) if records else None
    status_gate = evaluate_project_status_gate(db, project, project_status(project), dry_run=True)
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
            "severeIssues": len(severe),
            "artifacts": len(artifacts),
            "generatedArtifacts": len([item for item in artifacts if item.status == "已生成"]),
            "members": len(members),
            "milestones": len(milestones),
            "completedMilestones": done_milestones,
            "materialRequirements": len(materials),
            "requiredMaterials": initialization["requiredMaterials"],
            "completedRequiredMaterials": initialization["completedRequiredMaterials"],
        },
        "initialization": initialization,
        "initializationRecord": latest_record,
        "statusGate": status_gate,
    }


def _can_manage_project(db: Session, project: Project, user: dict[str, Any]) -> bool:
    if is_management_role(user.get("role")) or project.owner == user.get("name"):
        return True
    members = _filter_project_rows(db, ProjectMember, project.id)
    return any(row.user_id == user.get("id") and row.role in {"项目负责人", "项目管理员"} for row in members)


def map_project_profile(db: Session, project: Project, user: dict[str, Any]) -> dict[str, Any]:
    members = _filter_project_rows(db, ProjectMember, project.id)
    milestones = _filter_project_rows(db, ProjectMilestone, project.id)
    materials = _filter_project_rows(db, ProjectMaterialRequirement, project.id)
    records = _initialization_records(db, project.id)
    summary = map_project_summary(db, project)
    status = project_status(project)
    can_manage = _can_manage_project(db, project, user)
    close_gate = evaluate_project_status_gate(db, project, "已关闭")
    archive_gate = evaluate_project_status_gate(db, project, "已归档")
    return {
        **summary,
        "members": [map_project_member(db, row) for row in sorted(members, key=lambda item: (item.role, item.user_id))],
        "milestones": [map_milestone(row) for row in sorted(milestones, key=lambda item: (item.sort_order, item.id))],
        "materialRequirements": [map_material_requirement(row) for row in sorted(materials, key=lambda item: (item.sort_order, item.id))],
        "initializationRecords": [map_initialization_record(row) for row in records[:5]],
        "statusGates": {"close": close_gate, "archive": archive_gate},
        "actions": {
            "canEdit": can_manage and status not in {"已归档"},
            "canInitialize": can_manage and status in {"建档中", "进行中"},
            "canClose": can_manage and status in {"建档中", "进行中"} and close_gate["allowed"],
            "canArchive": can_manage and status == "已关闭" and archive_gate["allowed"],
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
    not_initialized = [item for item in summaries if not item["initialization"]["packageReady"]]
    gate_blocked = [item for item in summaries if item["statusGate"]["blockers"]]
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
            {"key": "notInitialized", "label": "待初始化", "value": len(not_initialized), "tone": "warning" if not_initialized else "success"},
            {"key": "gateBlocked", "label": "门禁阻断", "value": len(gate_blocked), "tone": "danger" if gate_blocked else "success"},
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
            "initializationPackage": True,
            "materialChecklist": True,
            "statusGate": True,
            "archiveGate": True,
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
        row = ProjectMilestone(id=f"PM-{project.id}-{order}", project_id=project.id, name=name, owner=owner, status="未开始", due_at=None, completed_at=None, sort_order=order)
        db.add(row)
        milestones.append(row)
    return milestones


def ensure_project_initialization_package(db: Session, project: Project, user: dict[str, Any] | None = None) -> dict[str, Any]:
    if user and user.get("id") and not _filter_project_rows(db, ProjectMember, project.id):
        ensure_project_member(db, project.id, user["id"], "项目负责人")
    add_default_milestones(db, project)
    created: dict[str, int] = {"materials": 0, "facts": 0, "chapters": 0, "artifacts": 0}
    for category, name, required, order in DEFAULT_MATERIAL_REQUIREMENTS:
        if not _existing_by_name(db, ProjectMaterialRequirement, project.id, "name", name):
            row = ProjectMaterialRequirement(
                id=f"PMR-{project.id}-{order}",
                project_id=project.id,
                category=category,
                name=name,
                required=required,
                status="待上传",
                source_type=None,
                source_id=None,
                sort_order=order,
            )
            db.add(row)
            created["materials"] += 1
    for index, (group, name, value, unit, source, status) in enumerate(DEFAULT_FACT_FRAME, start=1):
        if not _existing_by_name(db, FactItem, project.id, "name", name):
            row = FactItem(
                id=f"FI-{project.id}-{index}",
                project_id=project.id,
                fact_group=group,
                name=name,
                value=value,
                unit=unit,
                source=source,
                owner=project.owner,
                status=status,
            )
            db.add(row)
            created["facts"] += 1
    for no, title, owner, order in DEFAULT_CHAPTER_OUTLINE:
        if not _existing_by_name(db, ReportChapter, project.id, "chapter_no", no):
            row = ReportChapter(
                id=f"RC-{project.id}-{order}",
                project_id=project.id,
                chapter_no=no,
                title=title,
                owner=owner,
                status="未开始",
                citation_count=0,
                quality="提示",
                content=None,
            )
            db.add(row)
            created["chapters"] += 1
    for index, (name, fmt) in enumerate(DEFAULT_ARTIFACT_PLAN, start=1):
        if not _existing_by_name(db, Artifact, project.id, "name", name):
            row = Artifact(
                id=f"ART-{project.id}-{index}",
                project_id=project.id,
                name=name,
                format=fmt,
                status="可生成",
                updated_at=current_day(),
                storage_path=None,
                file_size=None,
                generated_at=None,
            )
            db.add(row)
            created["artifacts"] += 1
    summary = {"packageVersion": INITIALIZATION_PACKAGE_VERSION, "created": created}
    record = ProjectInitializationRecord(
        id=f"PIR-{project.id}-{int(time.time() * 1000)}",
        project_id=project.id,
        package_version=INITIALIZATION_PACKAGE_VERSION,
        status="已初始化",
        summary=summary,
        created_by=(user or {}).get("name") if user else None,
    )
    db.add(record)
    project.phase = project.phase or "项目建档"
    project.updated_at = now_utc()
    return summary


def can_change_status(project: Project, next_status: str) -> bool:
    status = project_status(project)
    allowed = {
        "建档中": {"进行中", "已关闭"},
        "进行中": {"已关闭"},
        "已关闭": {"进行中", "已归档"},
        "已归档": {"进行中"},
    }
    return next_status == status or next_status in allowed.get(status, set())


def evaluate_project_status_gate(db: Session, project: Project, target_status: str, dry_run: bool = False) -> dict[str, Any]:
    status = project_status(project)
    members = _filter_project_rows(db, ProjectMember, project.id)
    milestones = _filter_project_rows(db, ProjectMilestone, project.id)
    materials = _filter_project_rows(db, ProjectMaterialRequirement, project.id)
    facts = _filter_project_rows(db, FactItem, project.id)
    chapters = _filter_project_rows(db, ReportChapter, project.id)
    issues = _filter_project_rows(db, QualityIssue, project.id)
    artifacts = _filter_project_rows(db, Artifact, project.id)
    documents = _filter_project_rows(db, ProjectDocument, project.id)
    init = _current_initialization_status(members, milestones, materials, facts, chapters, artifacts, project)
    init["hasDocuments"] = len(documents) > 0
    open_issues = [item for item in issues if item.status != "已关闭"]
    blocking_issues = [item for item in open_issues if item.severity in {"阻断", "严重"}]
    running_tasks = _running_task_count(db, project.id)
    unapproved_chapters = [item for item in chapters if item.status != "已审核"]
    ungenerated_artifacts = [item for item in artifacts if item.status != "已生成"]
    incomplete_milestones = [item for item in milestones if item.status != "已完成"]
    missing_required_materials = [item for item in materials if item.required and item.status not in {"已上传", "已确认", "不适用"}]
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    def block(code: str, message: str, count: int = 1) -> None:
        blockers.append({"code": code, "message": message, "count": count})

    def warn(code: str, message: str, count: int = 1) -> None:
        warnings.append({"code": code, "message": message, "count": count})

    if target_status != status and not can_change_status(project, target_status):
        block("invalid_transition", f"当前状态 {status} 不允许变更为 {target_status}")
    if target_status in {"已关闭", "已归档"}:
        if not init["packageReady"]:
            block("initialization_incomplete", "项目初始化包未完整生成", len(init["missing"]))
        if blocking_issues:
            block("open_blocking_issues", "仍有严重/阻断质量问题未关闭", len(blocking_issues))
        if running_tasks:
            block("running_tasks", "仍有资料解析或质量检查任务未完成", running_tasks)
        if missing_required_materials:
            warn("missing_required_materials", "仍有必备资料未上传或确认", len(missing_required_materials))
        if unapproved_chapters:
            warn("unapproved_chapters", "仍有章节未审核", len(unapproved_chapters))
    if target_status == "已归档":
        if status != "已关闭":
            block("not_closed", "项目必须先关闭后才能归档")
        if unapproved_chapters:
            block("unapproved_chapters", "归档前必须完成章节审核", len(unapproved_chapters))
        if ungenerated_artifacts:
            block("ungenerated_artifacts", "归档前必须生成全部计划成果", len(ungenerated_artifacts))
        if incomplete_milestones:
            warn("incomplete_milestones", "仍有里程碑未完成", len(incomplete_milestones))
    checks = [
        {"key": "transition", "label": "状态流转合法", "passed": not any(item["code"] == "invalid_transition" for item in blockers)},
        {"key": "initialization", "label": "初始化包完整", "passed": init["packageReady"]},
        {"key": "quality", "label": "无严重/阻断问题", "passed": len(blocking_issues) == 0, "count": len(blocking_issues)},
        {"key": "tasks", "label": "无运行中任务", "passed": running_tasks == 0, "count": running_tasks},
        {"key": "chapters", "label": "章节审核", "passed": len(unapproved_chapters) == 0, "count": len(unapproved_chapters)},
        {"key": "artifacts", "label": "成果生成", "passed": len(ungenerated_artifacts) == 0, "count": len(ungenerated_artifacts)},
    ]
    return {
        "targetStatus": target_status,
        "currentStatus": status,
        "allowed": len(blockers) == 0,
        "blockers": blockers,
        "warnings": warnings,
        "checks": checks,
        "dryRun": dry_run,
    }
