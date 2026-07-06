"""project center v2.2 wizard drafts and region rules

Revision ID: 20260706_0008
Revises: 20260706_0007
Create Date: 2026-07-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260706_0008"
down_revision: Union[str, None] = "20260706_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return column in [item["name"] for item in inspector.get_columns(table)]


def upgrade() -> None:
    if _table_exists("projects"):
        with op.batch_alter_table("projects") as batch:
            if not _column_exists("projects", "region"):
                batch.add_column(sa.Column("region", sa.Text(), nullable=True))
            if not _column_exists("projects", "region_rule_id"):
                batch.add_column(sa.Column("region_rule_id", sa.Text(), nullable=True))
            if not _column_exists("projects", "initialization_rule_version"):
                batch.add_column(sa.Column("initialization_rule_version", sa.Text(), nullable=True))
            if not _column_exists("projects", "draft_source_id"):
                batch.add_column(sa.Column("draft_source_id", sa.Text(), nullable=True))

    if not _table_exists("project_wizard_drafts"):
        op.create_table(
            "project_wizard_drafts",
            sa.Column("id", sa.Text(), nullable=False),
            sa.Column("user_id", sa.Text(), nullable=True),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("step", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'草稿'")),
            sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["user_id"], ["app_users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_project_wizard_drafts_user", "project_wizard_drafts", ["user_id", "status", "updated_at"])

    if not _table_exists("project_region_rules"):
        op.create_table(
            "project_region_rules",
            sa.Column("id", sa.Text(), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("region", sa.Text(), nullable=False),
            sa.Column("project_type", sa.Text(), nullable=True),
            sa.Column("version", sa.Text(), nullable=False),
            sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'已发布'")),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("materials", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("facts", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("chapters", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("artifacts", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_project_region_rules_scope", "project_region_rules", ["region", "project_type", "status"])


def downgrade() -> None:
    if _table_exists("project_region_rules"):
        op.drop_table("project_region_rules")
    if _table_exists("project_wizard_drafts"):
        op.drop_table("project_wizard_drafts")
    if _table_exists("projects"):
        with op.batch_alter_table("projects") as batch:
            for column in ["draft_source_id", "initialization_rule_version", "region_rule_id", "region"]:
                if _column_exists("projects", column):
                    batch.drop_column(column)
