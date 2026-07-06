from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(Text)
    phase: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(Text)
    progress: Mapped[int] = mapped_column(Integer)
    risk: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class ProjectDocument(Base):
    __tablename__ = "project_documents"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(Text)
    parse_status: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)
    storage_path: Mapped[str | None] = mapped_column(Text)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    mime_type: Mapped[str | None] = mapped_column(Text)
    checksum: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    document_id: Mapped[str] = mapped_column(ForeignKey("project_documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    locator: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class FactItem(Base):
    __tablename__ = "fact_items"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    fact_group: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    value: Mapped[str] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)


class ReportChapter(Base):
    __tablename__ = "report_chapters"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    chapter_no: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    citation_count: Mapped[int] = mapped_column(Integer)
    quality: Mapped[str] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)


class ChapterCitation(Base):
    __tablename__ = "chapter_citations"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    chapter_id: Mapped[str] = mapped_column(ForeignKey("report_chapters.id", ondelete="CASCADE"))
    fact_id: Mapped[str | None] = mapped_column(ForeignKey("fact_items.id", ondelete="SET NULL"))
    document_id: Mapped[str | None] = mapped_column(ForeignKey("project_documents.id", ondelete="SET NULL"))
    chunk_id: Mapped[str | None] = mapped_column(ForeignKey("document_chunks.id", ondelete="SET NULL"))
    excerpt: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)


class QualityIssue(Base):
    __tablename__ = "quality_issues"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    severity: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    format: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)
    storage_path: Mapped[str | None] = mapped_column(Text)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    generated_at: Mapped[datetime | None]


class ParseJob(Base):
    __tablename__ = "parse_jobs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("project_documents.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    result: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class QualityCheckJob(Base):
    __tablename__ = "quality_check_jobs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class AppUser(Base):
    __tablename__ = "app_users"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    department: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    password_hash: Mapped[str | None] = mapped_column(Text)
    password_salt: Mapped[str | None] = mapped_column(Text)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class ReportTemplate(Base):
    __tablename__ = "report_templates"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    report_type: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)


class QualityRule(Base):
    __tablename__ = "quality_rules"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    code: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(Text)
    target: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean)
    description: Mapped[str] = mapped_column(Text)


class InvestmentEstimate(Base):
    __tablename__ = "investment_estimates"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(Text, server_default=text("'draft'"))
    input_snapshot: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    output: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    sensitivity: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    confirmed_by: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
