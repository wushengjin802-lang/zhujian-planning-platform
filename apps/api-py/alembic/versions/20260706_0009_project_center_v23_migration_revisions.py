"""project center v2.3 migration diff and revisions

Revision ID: 20260706_0009
Revises: 20260706_0008
Create Date: 2026-07-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260706_0009"
down_revision: Union[str, None] = "20260706_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("project_rule_migration_plans"):
        op.create_table(
            "project_rule_migration_plans",
            sa.Column("id", sa.Text(), nullable=False),
            sa.Column("project_id", sa.Text(), nullable=False),
            sa.Column("from_template_id", sa.Text(), nullable=True),
            sa.Column("from_template_version", sa.Text(), nullable=True),
            sa.Column("from_region_rule_id", sa.Text(), nullable=True),
            sa.Column("from_rule_version", sa.Text(), nullable=True),
            sa.Column("to_template_id", sa.Text(), nullable=True),
            sa.Column("to_template_version", sa.Text(), nullable=True),
            sa.Column("to_region_rule_id", sa.Text(), nullable=True),
            sa.Column("to_rule_version", sa.Text(), nullable=True),
            sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'待应用'")),
            sa.Column("risk_level", sa.Text(), nullable=False, server_default=sa.text("'一般'")),
            sa.Column("diff", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("applied_by", sa.Text(), nullable=True),
            sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_project_rule_migration_plans_project", "project_rule_migration_plans", ["project_id", "status", "created_at"])

    if not _table_exists("project_revisions"):
        op.create_table(
            "project_revisions",
            sa.Column("id", sa.Text(), nullable=False),
            sa.Column("project_id", sa.Text(), nullable=False),
            sa.Column("parent_revision_id", sa.Text(), nullable=True),
            sa.Column("revision_no", sa.Text(), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'草稿'")),
            sa.Column("baseline_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("closed_by", sa.Text(), nullable=True),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_project_revisions_project", "project_revisions", ["project_id", "status", "created_at"])
        op.create_unique_constraint("ux_project_revisions_no", "project_revisions", ["project_id", "revision_no"])


def downgrade() -> None:
    if _table_exists("project_revisions"):
        op.drop_table("project_revisions")
    if _table_exists("project_rule_migration_plans"):
        op.drop_table("project_rule_migration_plans")
