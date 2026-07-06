"""project center v2.1 initialization package and status gates

Revision ID: 20260706_0007
Revises: 20260706_0006
Create Date: 2026-07-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260706_0007"
down_revision: Union[str, None] = "20260706_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("project_material_requirements"):
        op.create_table(
            "project_material_requirements",
            sa.Column("id", sa.Text(), nullable=False),
            sa.Column("project_id", sa.Text(), nullable=False),
            sa.Column("category", sa.Text(), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'待上传'")),
            sa.Column("source_type", sa.Text(), nullable=True),
            sa.Column("source_id", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint("status in ('待上传','已上传','已确认','不适用')", name="ck_project_material_requirements_status"),
        )
        op.create_index("idx_project_material_requirements_project", "project_material_requirements", ["project_id", "sort_order"])
        op.create_index("idx_project_material_requirements_status", "project_material_requirements", ["project_id", "status"])
        op.create_unique_constraint("uq_project_material_requirements_name", "project_material_requirements", ["project_id", "category", "name"])

    if not _table_exists("project_initialization_records"):
        op.create_table(
            "project_initialization_records",
            sa.Column("id", sa.Text(), nullable=False),
            sa.Column("project_id", sa.Text(), nullable=False),
            sa.Column("package_version", sa.Text(), nullable=False),
            sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'已初始化'")),
            sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_project_initialization_records_project", "project_initialization_records", ["project_id", "created_at"])


def downgrade() -> None:
    if _table_exists("project_initialization_records"):
        op.drop_table("project_initialization_records")
    if _table_exists("project_material_requirements"):
        op.drop_table("project_material_requirements")
