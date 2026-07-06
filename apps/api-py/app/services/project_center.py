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
    ProjectRegionRule,
    ProjectRuleMigrationPlan,
    ProjectRevision,
    ProjectWizardDraft,
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
INITIALIZATION_PACKAGE_VERSION = "v2.4"
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

BUILTIN_REGION_RULES: list[dict[str, Any]] = [
    {
        "id": "BUILTIN-COMMON",
        "name": "通用项目初始化规则",
        "region": "全国",
        "projectType": "通用",
        "version": "v2.4",
        "status": "已发布",
        "description": "适用于未配置地区规则的项目，采用PDD一期通用资料、事实、章节和成果骨架。",
        "materials": [
            {"category": c, "name": n, "required": r, "sortOrder": o} for c, n, r, o in DEFAULT_MATERIAL_REQUIREMENTS
        ],
        "facts": [
            {"group": g, "name": n, "value": v, "unit": u, "source": src, "status": st} for g, n, v, u, src, st in DEFAULT_FACT_FRAME
        ],
        "chapters": [
            {"no": no, "title": title, "owner": owner, "sortOrder": order} for no, title, owner, order in DEFAULT_CHAPTER_OUTLINE
        ],
        "artifacts": [
            {"name": name, "format": fmt} for name, fmt in DEFAULT_ARTIFACT_PLAN
        ],
        "settings": {"requiresRegionCheck": False, "requiresSpecialMaterial": False},
    },
    {
        "id": "BUILTIN-GOV-INVESTMENT",
        "name": "政府投资项目规则",
        "region": "全国",
        "projectType": "政府投资",
        "version": "v2.4",
        "status": "已发布",
        "description": "面向政府投资类项目，额外关注财政资金、立项依据、绩效目标和用地合规。",
        "materials": [
            {"category": c, "name": n, "required": r, "sortOrder": o} for c, n, r, o in DEFAULT_MATERIAL_REQUIREMENTS
        ] + [
            {"category": "财政资料", "name": "财政资金来源或资金平衡说明", "required": True, "sortOrder": 20},
            {"category": "绩效资料", "name": "绩效目标或建设效益说明", "required": False, "sortOrder": 21},
        ],
        "facts": [
            {"group": g, "name": n, "value": v, "unit": u, "source": src, "status": st} for g, n, v, u, src, st in DEFAULT_FACT_FRAME
        ] + [
            {"group": "资金来源", "name": "财政资金比例", "value": "", "unit": "%", "source": "待补充", "status": "待确认"},
            {"group": "审批合规", "name": "立项审批依据", "value": "", "unit": None, "source": "待补充", "status": "待确认"},
        ],
        "chapters": [
            {"no": no, "title": title, "owner": owner, "sortOrder": order} for no, title, owner, order in DEFAULT_CHAPTER_OUTLINE
        ] + [
            {"no": "7", "title": "财政承受能力与绩效目标", "owner": "投资负责人", "sortOrder": 7},
        ],
        "artifacts": [
            {"name": name, "format": fmt} for name, fmt in DEFAULT_ARTIFACT_PLAN
        ] + [{"name": "政府投资合规清单.xlsx", "format": "Excel"}],
        "settings": {"requiresRegionCheck": True, "requiresSpecialMaterial": True},
    },
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


def map_project_draft(row: ProjectWizardDraft) -> dict[str, Any]:
    payload = row.payload or {}
    return {
        "id": row.id,
        "name": row.name,
        "step": row.step,
        "status": row.status,
        "payload": payload,
        "projectName": payload.get("name") or row.name,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def map_region_rule(row: ProjectRegionRule | dict[str, Any]) -> dict[str, Any]:
    if isinstance(row, dict):
        return {
            "id": row["id"],
            "name": row["name"],
            "region": row.get("region"),
            "projectType": row.get("projectType"),
            "version": row.get("version"),
            "status": row.get("status", "已发布"),
            "description": row.get("description"),
            "materials": row.get("materials", []),
            "facts": row.get("facts", []),
            "chapters": row.get("chapters", []),
            "artifacts": row.get("artifacts", []),
            "settings": row.get("settings", {}),
            "builtin": True,
        }
    return {
        "id": row.id,
        "name": row.name,
        "region": row.region,
        "projectType": row.project_type,
        "version": row.version,
        "status": row.status,
        "description": row.description,
        "materials": row.materials or [],
        "facts": row.facts or [],
        "chapters": row.chapters or [],
        "artifacts": row.artifacts or [],
        "settings": row.settings or {},
        "builtin": False,
    }




def _rule_key(item: dict[str, Any], fallback: str) -> str:
    return str(item.get("id") or item.get("key") or item.get("name") or item.get("title") or item.get("no") or fallback)


def _rule_label(item: dict[str, Any]) -> str:
    return str(item.get("name") or item.get("title") or item.get("label") or item.get("no") or "未命名项")


def _diff_rule_items(current_items: list[dict[str, Any]], target_items: list[dict[str, Any]], label: str) -> dict[str, Any]:
    current_map = {_rule_key(item, f"current-{index}"): item for index, item in enumerate(current_items, start=1)}
    target_map = {_rule_key(item, f"target-{index}"): item for index, item in enumerate(target_items, start=1)}
    current_keys = set(current_map)
    target_keys = set(target_map)
    added = [{"key": key, "label": _rule_label(target_map[key]), "item": target_map[key]} for key in sorted(target_keys - current_keys)]
    removed = [{"key": key, "label": _rule_label(current_map[key]), "item": current_map[key]} for key in sorted(current_keys - target_keys)]
    changed: list[dict[str, Any]] = []
    for key in sorted(current_keys & target_keys):
        before = current_map[key]
        after = target_map[key]
        if before != after:
            changed.append({"key": key, "label": _rule_label(after), "before": before, "after": after})
    return {"label": label, "added": added, "removed": removed, "changed": changed, "impactCount": len(added) + len(removed) + len(changed)}


def _project_current_blueprint(db: Session, project: Project) -> dict[str, Any]:
    materials = [
        {"name": row.name, "category": row.category, "required": bool(row.required), "sortOrder": row.sort_order}
        for row in sorted(_filter_project_rows(db, ProjectMaterialRequirement, project.id), key=lambda item: (item.sort_order, item.id))
    ]
    facts = [
        {"group": row.fact_group, "name": row.name, "unit": row.unit, "source": row.source, "status": row.status}
        for row in sorted(_filter_project_rows(db, FactItem, project.id), key=lambda item: item.id)
    ]
    chapters = [
        {"no": row.chapter_no, "title": row.title, "owner": row.owner}
        for row in sorted(_filter_project_rows(db, ReportChapter, project.id), key=lambda item: item.chapter_no)
    ]
    artifacts = [
        {"name": row.name, "format": row.format}
        for row in sorted(_filter_project_rows(db, Artifact, project.id), key=lambda item: item.id)
    ]
    return {"materials": materials, "facts": facts, "chapters": chapters, "artifacts": artifacts}


def preview_project_rule_migration(
    db: Session,
    project: Project,
    template_id: str | None = None,
    template_version: str | None = None,
    region_rule_id: str | None = None,
) -> dict[str, Any]:
    target_rule = get_region_rule_config(db, region_rule_id or getattr(project, "region_rule_id", None))
    current_blueprint = _project_current_blueprint(db, project)
    target_blueprint = {
        "materials": target_rule.get("materials") or [],
        "facts": target_rule.get("facts") or [],
        "chapters": target_rule.get("chapters") or [],
        "artifacts": target_rule.get("artifacts") or [],
    }
    sections = {
        "materials": _diff_rule_items(current_blueprint["materials"], target_blueprint["materials"], "资料清单"),
        "facts": _diff_rule_items(current_blueprint["facts"], target_blueprint["facts"], "事实框架"),
        "chapters": _diff_rule_items(current_blueprint["chapters"], target_blueprint["chapters"], "章节目录"),
        "artifacts": _diff_rule_items(current_blueprint["artifacts"], target_blueprint["artifacts"], "成果项"),
    }
    template_changed = (template_id or getattr(project, "template_id", None)) != getattr(project, "template_id", None) or (template_version or getattr(project, "template_version", None)) != getattr(project, "template_version", None)
    rule_changed = target_rule.get("id") != getattr(project, "region_rule_id", None) or target_rule.get("version") != getattr(project, "initialization_rule_version", None)
    impact_count = sum(section["impactCount"] for section in sections.values()) + (1 if template_changed else 0) + (1 if rule_changed else 0)
    if any(section["removed"] for section in sections.values()):
        risk_level = "严重"
    elif impact_count >= 5:
        risk_level = "一般"
    else:
        risk_level = "提示"
    recommendations: list[str] = []
    if template_changed:
        recommendations.append("模板版本发生变化，建议在迁移前确认章节样式和输出成果影响。")
    if rule_changed:
        recommendations.append("初始化规则发生变化，建议确认新增资料、事实和成果项是否适用于当前项目。")
    if any(section["removed"] for section in sections.values()):
        recommendations.append("目标规则少于当前项目骨架，系统不会自动删除现有资料、事实、章节或成果项。")
    if not recommendations:
        recommendations.append("未发现明显结构差异，可按需生成迁移计划。")
    return {
        "from": {
            "templateId": getattr(project, "template_id", None),
            "templateVersion": getattr(project, "template_version", None),
            "regionRuleId": getattr(project, "region_rule_id", None),
            "ruleVersion": getattr(project, "initialization_rule_version", None),
        },
        "to": {
            "templateId": template_id or getattr(project, "template_id", None),
            "templateVersion": template_version or getattr(project, "template_version", None),
            "regionRuleId": target_rule.get("id"),
            "ruleVersion": target_rule.get("version"),
            "ruleName": target_rule.get("name"),
        },
        "sections": sections,
        "impactCount": impact_count,
        "riskLevel": risk_level,
        "templateChanged": template_changed,
        "ruleChanged": rule_changed,
        "recommendations": recommendations,
    }


def map_rule_migration_plan(row: ProjectRuleMigrationPlan) -> dict[str, Any]:
    diff = row.diff or {}
    approval = diff.get("approval") or {}
    rejection = diff.get("rejection") or {}
    rollback = diff.get("rollback") or {}
    actions = migration_plan_actions(row)
    return {
        "id": row.id,
        "projectId": row.project_id,
        "fromTemplateId": row.from_template_id,
        "fromTemplateVersion": row.from_template_version,
        "fromRegionRuleId": row.from_region_rule_id,
        "fromRuleVersion": row.from_rule_version,
        "toTemplateId": row.to_template_id,
        "toTemplateVersion": row.to_template_version,
        "toRegionRuleId": row.to_region_rule_id,
        "toRuleVersion": row.to_rule_version,
        "status": row.status,
        "riskLevel": row.risk_level,
        "diff": diff,
        "approval": approval,
        "rejection": rejection,
        "rollback": rollback,
        "actions": actions,
        "createdBy": row.created_by,
        "appliedBy": row.applied_by,
        "appliedAt": row.applied_at.isoformat() if row.applied_at else None,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def _project_migration_plans(db: Session, project_id: str) -> list[ProjectRuleMigrationPlan]:
    rows = _filter_project_rows(db, ProjectRuleMigrationPlan, project_id)
    return sorted(rows, key=lambda item: getattr(item, "created_at", None) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)


def create_rule_migration_plan(
    db: Session,
    project: Project,
    user: dict[str, Any],
    template_id: str | None = None,
    template_version: str | None = None,
    region_rule_id: str | None = None,
) -> ProjectRuleMigrationPlan:
    diff = preview_project_rule_migration(db, project, template_id, template_version, region_rule_id)
    row = ProjectRuleMigrationPlan(
        id=f"PRMP-{int(time.time() * 1000)}",
        project_id=project.id,
        from_template_id=diff["from"].get("templateId"),
        from_template_version=diff["from"].get("templateVersion"),
        from_region_rule_id=diff["from"].get("regionRuleId"),
        from_rule_version=diff["from"].get("ruleVersion"),
        to_template_id=diff["to"].get("templateId"),
        to_template_version=diff["to"].get("templateVersion"),
        to_region_rule_id=diff["to"].get("regionRuleId"),
        to_rule_version=diff["to"].get("ruleVersion"),
        status="待审批",
        risk_level=diff["riskLevel"],
        diff=diff,
        created_by=user.get("name"),
        applied_by=None,
        applied_at=None,
    )
    db.add(row)
    return row


def migration_plan_actions(row: ProjectRuleMigrationPlan) -> dict[str, bool]:
    status = row.status
    return {
        "canApprove": status == "待审批",
        "canReject": status == "待审批",
        "canApply": status in {"已审批", "待应用"},
        "canRollback": status == "已应用",
        "canViewDiff": True,
    }


def approve_rule_migration_plan(db: Session, plan: ProjectRuleMigrationPlan, user: dict[str, Any], comment: str | None = None) -> ProjectRuleMigrationPlan:
    if plan.status not in {"待审批", "已审批"}:
        raise ValueError(f"当前迁移计划状态 {plan.status} 不允许审批通过")
    diff = dict(plan.diff or {})
    diff["approval"] = {
        "approvedBy": user.get("name"),
        "approvedAt": now_utc().isoformat(),
        "comment": comment,
    }
    plan.diff = diff
    plan.status = "已审批"
    plan.updated_at = now_utc()
    return plan


def reject_rule_migration_plan(db: Session, plan: ProjectRuleMigrationPlan, user: dict[str, Any], comment: str | None = None) -> ProjectRuleMigrationPlan:
    if plan.status not in {"待审批", "已审批"}:
        raise ValueError(f"当前迁移计划状态 {plan.status} 不允许驳回")
    diff = dict(plan.diff or {})
    diff["rejection"] = {
        "rejectedBy": user.get("name"),
        "rejectedAt": now_utc().isoformat(),
        "comment": comment,
    }
    plan.diff = diff
    plan.status = "已驳回"
    plan.updated_at = now_utc()
    return plan


def apply_rule_migration_plan(db: Session, project: Project, plan: ProjectRuleMigrationPlan, user: dict[str, Any]) -> dict[str, Any]:
    if plan.status == "已应用":
        return plan.diff or {}
    if plan.status not in {"已审批", "待应用"}:
        raise ValueError("迁移计划必须先审批通过后才能应用")
    previous = {
        "templateId": project.template_id,
        "templateVersion": project.template_version,
        "regionRuleId": project.region_rule_id,
        "ruleVersion": project.initialization_rule_version,
    }
    project.template_id = plan.to_template_id
    project.template_version = plan.to_template_version
    project.region_rule_id = plan.to_region_rule_id
    project.initialization_rule_version = plan.to_rule_version
    project.updated_at = now_utc()
    summary = ensure_project_initialization_package(db, project, user)
    plan.status = "已应用"
    plan.applied_by = user.get("name")
    plan.applied_at = now_utc()
    plan.updated_at = now_utc()
    diff = dict(plan.diff or {})
    diff["previousProjectSettings"] = previous
    diff["appliedSummary"] = summary
    plan.diff = diff
    return diff


def rollback_rule_migration_plan(db: Session, project: Project, plan: ProjectRuleMigrationPlan, user: dict[str, Any], comment: str | None = None) -> dict[str, Any]:
    if plan.status != "已应用":
        raise ValueError("仅已应用的迁移计划可回滚")
    diff = dict(plan.diff or {})
    previous = diff.get("previousProjectSettings") or {
        "templateId": plan.from_template_id,
        "templateVersion": plan.from_template_version,
        "regionRuleId": plan.from_region_rule_id,
        "ruleVersion": plan.from_rule_version,
    }
    project.template_id = previous.get("templateId")
    project.template_version = previous.get("templateVersion")
    project.region_rule_id = previous.get("regionRuleId")
    project.initialization_rule_version = previous.get("ruleVersion")
    project.updated_at = now_utc()
    diff["rollback"] = {
        "rolledBackBy": user.get("name"),
        "rolledBackAt": now_utc().isoformat(),
        "comment": comment,
        "restored": previous,
        "note": "回滚只恢复项目模板/地区规则指针，不删除迁移期间补齐的资料、事实、章节或成果项。",
    }
    plan.diff = diff
    plan.status = "已回滚"
    plan.updated_at = now_utc()
    return diff


def _project_revision_rows(db: Session, project_id: str) -> list[ProjectRevision]:
    rows = _filter_project_rows(db, ProjectRevision, project_id)
    return sorted(rows, key=lambda item: getattr(item, "created_at", None) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)


def _project_revision_no(db: Session, project_id: str) -> str:
    rows = _filter_project_rows(db, ProjectRevision, project_id)
    return f"R{len(rows) + 1:03d}"


def _project_revision_snapshot(db: Session, project: Project) -> dict[str, Any]:
    summary = map_project_summary(db, project)
    return {
        "project": {key: summary.get(key) for key in ["id", "code", "name", "type", "location", "phase", "status", "owner", "templateId", "templateVersion", "region", "regionRuleId", "initializationRuleVersion"]},
        "stats": summary.get("stats"),
        "initialization": summary.get("initialization"),
        "statusGate": summary.get("statusGate"),
    }


def map_project_revision(row: ProjectRevision) -> dict[str, Any]:
    return {
        "id": row.id,
        "projectId": row.project_id,
        "parentRevisionId": row.parent_revision_id,
        "revisionNo": row.revision_no,
        "title": row.title,
        "reason": row.reason,
        "status": row.status,
        "baselineSnapshot": row.baseline_snapshot or {},
        "createdBy": row.created_by,
        "closedBy": row.closed_by,
        "closedAt": row.closed_at.isoformat() if row.closed_at else None,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def create_project_revision(db: Session, project: Project, user: dict[str, Any], title: str | None = None, reason: str | None = None) -> ProjectRevision:
    active_rows = [row for row in _filter_project_rows(db, ProjectRevision, project.id) if row.status == "草稿"]
    if active_rows:
        return active_rows[0]
    rows = _project_revision_rows(db, project.id)
    parent = rows[0] if rows else None
    row = ProjectRevision(
        id=f"PRV-{int(time.time() * 1000)}",
        project_id=project.id,
        parent_revision_id=parent.id if parent else None,
        revision_no=_project_revision_no(db, project.id),
        title=title or f"{project.name} 修订",
        reason=reason,
        status="草稿",
        baseline_snapshot=_project_revision_snapshot(db, project),
        created_by=user.get("name"),
        closed_by=None,
        closed_at=None,
    )
    db.add(row)
    return row


def close_project_revision(db: Session, revision: ProjectRevision, user: dict[str, Any], status: str = "已确认") -> ProjectRevision:
    revision.status = status
    revision.closed_by = user.get("name")
    revision.closed_at = now_utc()
    revision.updated_at = now_utc()
    return revision


def list_region_rules(db: Session) -> list[dict[str, Any]]:
    fake = _rows(db, ProjectRegionRule)
    db_rules = fake if fake is not None else db.scalars(select(ProjectRegionRule).where(ProjectRegionRule.status != "已停用").order_by(ProjectRegionRule.region, ProjectRegionRule.name)).all()
    rows = [map_region_rule(rule) for rule in db_rules if getattr(rule, "status", "已发布") != "已停用"]
    seen = {item["id"] for item in rows}
    rows.extend(map_region_rule(rule) for rule in BUILTIN_REGION_RULES if rule["id"] not in seen)
    return rows


def get_region_rule_config(db: Session, rule_id: str | None) -> dict[str, Any]:
    rules = list_region_rules(db)
    if rule_id:
        match = next((rule for rule in rules if rule["id"] == rule_id), None)
        if match:
            return match
    return next(rule for rule in rules if rule["id"] == "BUILTIN-COMMON")


def _project_initialization_blueprint(db: Session, project: Project) -> dict[str, list[dict[str, Any]] | dict[str, Any] | str | None]:
    rule = get_region_rule_config(db, getattr(project, "region_rule_id", None))
    return {
        "ruleId": rule["id"],
        "ruleName": rule["name"],
        "ruleVersion": rule.get("version"),
        "materials": rule.get("materials") or [],
        "facts": rule.get("facts") or [],
        "chapters": rule.get("chapters") or [],
        "artifacts": rule.get("artifacts") or [],
        "settings": rule.get("settings") or {},
    }


def list_project_drafts(db: Session, user: dict[str, Any]) -> list[dict[str, Any]]:
    fake = _rows(db, ProjectWizardDraft)
    rows = fake if fake is not None else db.scalars(select(ProjectWizardDraft).where(ProjectWizardDraft.user_id == user.get("id"), ProjectWizardDraft.status == "草稿").order_by(ProjectWizardDraft.updated_at.desc(), ProjectWizardDraft.id.desc())).all()
    return [map_project_draft(row) for row in rows if row.user_id == user.get("id") and row.status == "草稿"]


def upsert_project_draft(db: Session, user: dict[str, Any], payload: dict[str, Any], draft_id: str | None = None, step: int = 0, name: str | None = None) -> ProjectWizardDraft:
    row = db.get(ProjectWizardDraft, draft_id) if draft_id and not getattr(db, "rows_by_model", None) else None
    fake = _rows(db, ProjectWizardDraft)
    if fake is not None and draft_id:
        row = next((item for item in fake if item.id == draft_id and item.user_id == user.get("id")), None)
    if not row:
        row = ProjectWizardDraft(
            id=draft_id or f"PWD-{int(time.time() * 1000)}",
            user_id=user.get("id"),
            name=name or payload.get("name") or "未命名项目草稿",
            step=step,
            status="草稿",
            payload=payload,
        )
        db.add(row)
    else:
        row.name = name or payload.get("name") or row.name
        row.step = step
        row.payload = payload
        row.status = "草稿"
        row.updated_at = now_utc()
    return row


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
        "region": getattr(project, "region", None),
        "regionRuleId": getattr(project, "region_rule_id", None),
        "initializationRuleVersion": getattr(project, "initialization_rule_version", None),
        "draftSourceId": getattr(project, "draft_source_id", None),
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


def is_project_readonly(project: Project) -> bool:
    return project_status(project) in {"已关闭", "已归档"}


def project_readonly_reason(project: Project) -> str | None:
    status = project_status(project)
    if status == "已关闭":
        return "项目已关闭，仅允许重新打开、归档、创建修订和受控迁移审批操作。"
    if status == "已归档":
        return "项目已归档，项目中心基础资料只读，仅允许重新打开或复制项目。"
    return None


def assert_project_writable(project: Project, action: str = "修改项目") -> None:
    reason = project_readonly_reason(project)
    if reason:
        raise ValueError(f"{action}被项目状态只读边界阻止：{reason}")


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
    migration_plans = _project_migration_plans(db, project.id)
    revisions = _project_revision_rows(db, project.id)
    summary = map_project_summary(db, project)
    status = project_status(project)
    can_manage = _can_manage_project(db, project, user)
    close_gate = evaluate_project_status_gate(db, project, "已关闭")
    archive_gate = evaluate_project_status_gate(db, project, "已归档")
    migration_preview = preview_project_rule_migration(db, project, getattr(project, "template_id", None), getattr(project, "template_version", None), getattr(project, "region_rule_id", None))
    return {
        **summary,
        "members": [map_project_member(db, row) for row in sorted(members, key=lambda item: (item.role, item.user_id))],
        "milestones": [map_milestone(row) for row in sorted(milestones, key=lambda item: (item.sort_order, item.id))],
        "materialRequirements": [map_material_requirement(row) for row in sorted(materials, key=lambda item: (item.sort_order, item.id))],
        "initializationRecords": [map_initialization_record(row) for row in records[:5]],
        "migrationPlans": [map_rule_migration_plan(row) for row in migration_plans[:5]],
        "revisions": [map_project_revision(row) for row in revisions[:8]],
        "migrationPreview": migration_preview,
        "statusGates": {"close": close_gate, "archive": archive_gate},
        "actions": {
            "readonly": is_project_readonly(project),
            "readonlyReason": project_readonly_reason(project),
            "canEdit": can_manage and not is_project_readonly(project),
            "canInitialize": can_manage and status in {"建档中", "进行中"},
            "canCreateMigrationPlan": can_manage and status in {"建档中", "进行中", "已关闭"},
            "canApproveMigrationPlan": can_manage and status in {"建档中", "进行中", "已关闭"},
            "canRejectMigrationPlan": can_manage and status in {"建档中", "进行中", "已关闭"},
            "canApplyMigrationPlan": can_manage and status in {"建档中", "进行中"},
            "canRollbackMigrationPlan": can_manage and status in {"建档中", "进行中"},
            "canCreateRevision": can_manage and status in {"已关闭", "已归档", "进行中"},
            "canCloseRevision": can_manage,
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
    region_rules = list_region_rules(db)
    drafts = list_project_drafts(db, user)
    return {
        "generatedAt": now_utc().isoformat(),
        "metrics": [
            {"key": "total", "label": "项目总数", "value": len(summaries), "tone": "primary"},
            {"key": "active", "label": "进行中", "value": len(active), "tone": "success"},
            {"key": "notInitialized", "label": "待初始化", "value": len(not_initialized), "tone": "warning" if not_initialized else "success"},
            {"key": "drafts", "label": "建档草稿", "value": len(drafts), "tone": "warning" if drafts else "info"},
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
        "regionRules": region_rules,
        "wizardDrafts": drafts,
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
            "wizardDraft": True,
            "regionRuleBinding": True,
            "templateDrivenInitialization": True,
            "migrationDiffPreview": True,
            "migrationPlanApply": True,
            "projectRevisionChain": True,
            "migrationApprovalFlow": True,
            "migrationRollback": True,
            "readonlyProjectBoundary": True,
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
    blueprint = _project_initialization_blueprint(db, project)
    created: dict[str, int] = {"materials": 0, "facts": 0, "chapters": 0, "artifacts": 0}

    for index, item in enumerate(blueprint["materials"], start=1):
        name = item.get("name") or "未命名资料"
        if not _existing_by_name(db, ProjectMaterialRequirement, project.id, "name", name):
            row = ProjectMaterialRequirement(
                id=f"PMR-{project.id}-{item.get('sortOrder') or index}",
                project_id=project.id,
                category=item.get("category") or "项目资料",
                name=name,
                required=bool(item.get("required", True)),
                status="待上传",
                source_type=None,
                source_id=None,
                sort_order=int(item.get("sortOrder") or index),
            )
            db.add(row)
            created["materials"] += 1

    for index, item in enumerate(blueprint["facts"], start=1):
        name = item.get("name") or "未命名事实"
        if not _existing_by_name(db, FactItem, project.id, "name", name):
            row = FactItem(
                id=f"FI-{project.id}-{index}",
                project_id=project.id,
                fact_group=item.get("group") or item.get("factGroup") or "项目事实",
                name=name,
                value=item.get("value") or "",
                unit=item.get("unit"),
                source=item.get("source") or "待补充",
                owner=project.owner,
                status=item.get("status") or "待确认",
            )
            db.add(row)
            created["facts"] += 1

    for index, item in enumerate(blueprint["chapters"], start=1):
        no = str(item.get("no") or index)
        if not _existing_by_name(db, ReportChapter, project.id, "chapter_no", no):
            row = ReportChapter(
                id=f"RC-{project.id}-{item.get('sortOrder') or index}",
                project_id=project.id,
                chapter_no=no,
                title=item.get("title") or f"第{index}章",
                owner=item.get("owner") or "报告负责人",
                status="未开始",
                citation_count=0,
                quality="提示",
                content=None,
            )
            db.add(row)
            created["chapters"] += 1

    for index, item in enumerate(blueprint["artifacts"], start=1):
        name = item.get("name") or f"成果{index}"
        if not _existing_by_name(db, Artifact, project.id, "name", name):
            row = Artifact(
                id=f"ART-{project.id}-{index}",
                project_id=project.id,
                name=name,
                format=item.get("format") or "Word",
                status="可生成",
                updated_at=current_day(),
                storage_path=None,
                file_size=None,
                generated_at=None,
            )
            db.add(row)
            created["artifacts"] += 1
    project.region_rule_id = getattr(project, "region_rule_id", None) or blueprint.get("ruleId")
    project.initialization_rule_version = str(blueprint.get("ruleVersion") or INITIALIZATION_PACKAGE_VERSION)
    summary = {
        "packageVersion": INITIALIZATION_PACKAGE_VERSION,
        "ruleId": blueprint.get("ruleId"),
        "ruleName": blueprint.get("ruleName"),
        "ruleVersion": blueprint.get("ruleVersion"),
        "created": created,
        "expected": {
            "materials": len(blueprint["materials"]),
            "facts": len(blueprint["facts"]),
            "chapters": len(blueprint["chapters"]),
            "artifacts": len(blueprint["artifacts"]),
        },
    }
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
