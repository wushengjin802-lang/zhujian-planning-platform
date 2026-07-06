"""project center v2.0 fields, milestones and indexes

Revision ID: 20260706_0006
Revises: 20260706_0005
Create Date: 2026-07-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260706_0006"
down_revision: Union[str, None] = "20260706_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {item["name"] for item in inspector.get_columns(table)}
    if column.name not in existing:
        op.add_column(table, column)


def upgrade() -> None:
    _add_column_if_missing("projects", sa.Column("code", sa.Text(), nullable=True))
    _add_column_if_missing("projects", sa.Column("status", sa.Text(), nullable=True))
    _add_column_if_missing("projects", sa.Column("confidentiality", sa.Text(), nullable=True))
    _add_column_if_missing("projects", sa.Column("template_id", sa.Text(), nullable=True))
    _add_column_if_missing("projects", sa.Column("template_version", sa.Text(), nullable=True))
    _add_column_if_missing("projects", sa.Column("planned_start", sa.Text(), nullable=True))
    _add_column_if_missing("projects", sa.Column("planned_end", sa.Text(), nullable=True))
    _add_column_if_missing("projects", sa.Column("description", sa.Text(), nullable=True))
    _add_column_if_missing("projects", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))

    op.execute("update projects set status = coalesce(status, '进行中')")
    op.execute("update projects set confidentiality = coalesce(confidentiality, '内部')")
    op.execute("update projects set code = coalesce(code, id)")

    op.execute("create unique index if not exists ux_projects_code on projects(code)")
    op.execute("create index if not exists idx_projects_status on projects(status)")
    op.execute("create index if not exists idx_projects_template on projects(template_id, template_version)")

    op.create_table(
        "project_milestones",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("owner", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'未开始'")),
        sa.Column("due_at", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status in ('未开始','进行中','已完成','已逾期')", name="ck_project_milestones_status"),
    )
    op.create_index("idx_project_milestones_project", "project_milestones", ["project_id", "sort_order"])


def downgrade() -> None:
    op.drop_table("project_milestones")
    op.execute("drop index if exists idx_projects_template")
    op.execute("drop index if exists idx_projects_status")
    op.execute("drop index if exists ux_projects_code")
    # Keep added project columns on downgrade to avoid destructive loss in environments
    # where project data may already depend on them.
