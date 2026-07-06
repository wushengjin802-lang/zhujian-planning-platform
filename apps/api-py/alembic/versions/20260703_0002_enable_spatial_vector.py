"""enable PostGIS and pgvector physical columns

Revision ID: 20260703_0002
Revises: 20260703_0001
Create Date: 2026-07-03
"""

from alembic import op

revision = "20260703_0002"
down_revision = "20260703_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("set search_path to public")
    op.execute("create extension if not exists postgis")
    op.execute("create extension if not exists vector")
    op.execute("alter table document_chunks add column if not exists embedding vector(1536)")
    op.execute(
        """
        create index if not exists idx_document_chunks_embedding
        on document_chunks using ivfflat (embedding vector_cosine_ops)
        with (lists = 100)
        """
    )


def downgrade() -> None:
    op.execute("drop index if exists idx_document_chunks_embedding")
    op.execute("alter table document_chunks drop column if exists embedding")
