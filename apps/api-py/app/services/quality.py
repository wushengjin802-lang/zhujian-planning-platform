from __future__ import annotations

import time
import re

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.models import (
    AuditLog,
    FactItem,
    ProjectDocument,
    QualityCheckJob,
    QualityIssue,
    ReportChapter,
)


def run_quality_check(db: Session, project_id: str | None) -> dict:
    job = QualityCheckJob(
        id=f"QC-{int(time.time() * 1000)}",
        project_id=project_id,
        status="completed",
        message="质量检查已完成，规则命中结果已写入问题清单。",
    )
    db.add(job)
    created: list[str] = []
    if project_id:
        created.extend(check_missing_document_chunks(db, project_id))
        created.extend(check_fact_conflicts(db, project_id))
        created.extend(check_numeric_anomalies(db, project_id))
        created.extend(check_low_citations(db, project_id))
        created.extend(check_unapproved_chapters(db, project_id))
    db.add(
        AuditLog(
            actor="system",
            action="run_quality_check",
            entity_type="quality_check_job",
            entity_id=job.id,
            detail={"projectId": project_id, "createdIssues": created},
        )
    )
    db.commit()
    return {"id": job.id, "projectId": project_id, "status": job.status, "message": job.message, "createdIssues": created}


def check_missing_document_chunks(db: Session, project_id: str) -> list[str]:
    rows = db.execute(
        text(
            """
            select d.id, d.name
            from project_documents d
            left join document_chunks c on c.document_id = d.id
            where d.project_id = :project_id and d.parse_status <> '已解析'
            group by d.id, d.name
            having count(c.id) = 0
            """
        ),
        {"project_id": project_id},
    ).mappings()
    return [
        ensure_issue(
            db,
            project_id,
            "严重",
            "资料缺失",
            f"资料《{row['name']}》尚未形成可引用解析切片",
            "资料管理员",
            f"document:{row['id']}",
        )
        for row in rows
    ]


def check_fact_conflicts(db: Session, project_id: str) -> list[str]:
    conflict_count = db.scalar(select(func.count()).select_from(FactItem).where(FactItem.project_id == project_id, FactItem.status == "有冲突")) or 0
    if not conflict_count:
        return []
    return [
        ensure_issue(
            db,
            project_id,
            "严重",
            "事实冲突",
            f"仍存在 {conflict_count} 条未处理事实冲突",
            "项目负责人",
            "facts:conflict",
        )
    ]


def check_numeric_anomalies(db: Session, project_id: str) -> list[str]:
    issues: list[str] = []
    facts = db.scalars(select(FactItem).where(FactItem.project_id == project_id).order_by(FactItem.id)).all()
    for fact in facts:
        value = parse_number(fact.value)
        if value is None:
            continue
        name = fact.name
        if any(keyword in name for keyword in ["投资", "费用", "金额"]) and value <= 0:
            issues.append(create_numeric_issue(db, project_id, fact, "投资费用类指标必须大于 0"))
        if any(keyword in name for keyword in ["面积", "规模"]) and value <= 0:
            issues.append(create_numeric_issue(db, project_id, fact, "面积规模类指标必须大于 0"))
        if any(keyword in name for keyword in ["周期", "工期"]) and (value <= 0 or value > 120):
            issues.append(create_numeric_issue(db, project_id, fact, "周期工期类指标应在 1 至 120 个月范围内"))
    return issues


def create_numeric_issue(db: Session, project_id: str, fact: FactItem, message: str) -> str:
    return ensure_issue(
        db,
        project_id,
        "严重",
        "数值异常",
        f"{fact.name}={fact.value}{fact.unit or ''}，{message}",
        fact.owner,
        f"fact:{fact.id}:numeric",
    )


def parse_number(value: str) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
    return float(match.group(0)) if match else None


def check_low_citations(db: Session, project_id: str) -> list[str]:
    chapters = db.scalars(
        select(ReportChapter)
        .where(ReportChapter.project_id == project_id, ReportChapter.citation_count < 1)
        .order_by(ReportChapter.chapter_no)
    ).all()
    return [
        ensure_issue(
            db,
            project_id,
            "一般",
            "引用不足",
            f"章节 {chapter.chapter_no}《{chapter.title}》缺少引用依据",
            chapter.owner,
            f"chapter:{chapter.id}:citations",
        )
        for chapter in chapters
    ]


def check_unapproved_chapters(db: Session, project_id: str) -> list[str]:
    unapproved = db.scalar(
        select(func.count()).select_from(ReportChapter).where(ReportChapter.project_id == project_id, ReportChapter.status != "已审核")
    ) or 0
    if not unapproved:
        return []
    return [
        ensure_issue(
            db,
            project_id,
            "阻断",
            "发布门禁",
            f"仍有 {unapproved} 个章节未完成审核，成果归档前必须关闭",
            "专业审核人",
            "chapters:approval",
        )
    ]


def ensure_issue(
    db: Session,
    project_id: str,
    severity: str,
    issue_type: str,
    title: str,
    owner: str,
    evidence_key: str,
) -> str:
    existing = db.scalars(
        select(QualityIssue).where(
            QualityIssue.project_id == project_id,
            QualityIssue.type == issue_type,
            QualityIssue.title == title,
            QualityIssue.status != "已关闭",
        )
    ).first()
    if existing:
        return existing.id
    issue = QualityIssue(
        id=f"Q{int(time.time() * 1000)}{abs(hash(evidence_key)) % 10000}",
        project_id=project_id,
        severity=severity,
        type=issue_type,
        title=title,
        owner=owner,
        status="待处理",
    )
    db.add(issue)
    return issue.id
