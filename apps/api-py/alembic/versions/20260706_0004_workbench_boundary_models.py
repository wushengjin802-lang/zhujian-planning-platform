"""add persistent workbench boundary models

Revision ID: 20260706_0004
Revises: 20260703_0003
Create Date: 2026-07-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260706_0004"
down_revision: Union[str, None] = "20260703_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "work_items",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column("source_type", sa.Text(), nullable=True),
        sa.Column("source_id", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("priority", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'待处理'")),
        sa.Column("owner", sa.Text(), nullable=False),
        sa.Column("assignee_id", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("route", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assignee_id"], ["app_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("priority in ('P0','P1','P2','P3')", name="ck_work_items_priority"),
        sa.CheckConstraint("status in ('待领取','待处理','处理中','已完成','已取消')", name="ck_work_items_status"),
    )
    op.create_index("idx_work_items_project_status", "work_items", ["project_id", "status"])
    op.create_index("idx_work_items_assignee_status", "work_items", ["assignee_id", "status"])
    op.create_index("idx_work_items_source", "work_items", ["source_type", "source_id"])

    op.create_table(
        "review_tasks",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'待审核'")),
        sa.Column("submitter", sa.Text(), nullable=False),
        sa.Column("reviewer_id", sa.Text(), nullable=True),
        sa.Column("route", sa.Text(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["app_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("priority in ('P0','P1','P2','P3')", name="ck_review_tasks_priority"),
        sa.CheckConstraint("status in ('待审核','审核中','已通过','已退回','已取消')", name="ck_review_tasks_status"),
    )
    op.create_index("idx_review_tasks_project_status", "review_tasks", ["project_id", "status"])
    op.create_index("idx_review_tasks_reviewer_status", "review_tasks", ["reviewer_id", "status"])
    op.create_index("idx_review_tasks_target", "review_tasks", ["target_type", "target_id"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("route", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=True),
        sa.Column("source_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'未读'")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("level in ('success','info','warning','danger')", name="ck_notifications_level"),
        sa.CheckConstraint("status in ('未读','已读','已归档')", name="ck_notifications_status"),
    )
    op.create_index("idx_notifications_user_status", "notifications", ["user_id", "status"])
    op.create_index("idx_notifications_project_status", "notifications", ["project_id", "status"])
    op.create_index("idx_notifications_source", "notifications", ["source_type", "source_id"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("review_tasks")
    op.drop_table("work_items")
