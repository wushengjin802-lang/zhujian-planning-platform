"""project center v2.3 migration diff and revision chain

Revision ID: 20260706_0009
Revises: 20260706_0008
Create Date: 2026-07-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260706_0009"
down_revision = "20260706_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_rule_migrations",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("project_id", sa.Text(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_rule_id", sa.Text(), nullable=True),
        sa.Column("from_rule_version", sa.Text(), nullable=True),
        sa.Column("to_rule_id", sa.Text(), nullable=False),
        sa.Column("to_rule_version", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="待应用", nullable=False),
        sa.Column("diff", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("applied_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_project_rule_migrations_project", "project_rule_migrations", ["project_id", "created_at"])

    op.create_table(
        "project_revisions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("project_id", sa.Text(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="草稿", nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_project_revisions_project", "project_revisions", ["project_id", "revision_no"])


def downgrade() -> None:
    op.drop_index("ix_project_revisions_project", table_name="project_revisions")
    op.drop_table("project_revisions")
    op.drop_index("ix_project_rule_migrations_project", table_name="project_rule_migrations")
    op.drop_table("project_rule_migrations")
