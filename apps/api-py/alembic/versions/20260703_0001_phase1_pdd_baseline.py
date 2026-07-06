"""phase 1 PDD baseline with PostGIS and pgvector hooks

Revision ID: 20260703_0001
Revises:
Create Date: 2026-07-03
"""

from alembic import op

revision = "20260703_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("set search_path to public")
    op.execute(
        """
        do $$
        begin
          begin
            execute 'create extension if not exists postgis';
          exception when undefined_file or insufficient_privilege or feature_not_supported then
            raise notice 'PostGIS extension is not available or permission is insufficient.';
          end;

          begin
            execute 'create extension if not exists vector';
          exception when undefined_file or insufficient_privilege or feature_not_supported then
            raise notice 'pgvector extension is not available or permission is insufficient.';
          end;
        end $$;
        """
    )
    op.execute(
        """
        create table if not exists projects (
          id text primary key,
          name text not null,
          type text not null,
          location text not null,
          phase text not null,
          owner text not null,
          progress integer not null default 0 check (progress between 0 and 100),
          risk text not null check (risk in ('阻断', '严重', '一般', '提示')),
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );

        create table if not exists project_documents (
          id text primary key,
          project_id text not null references projects(id) on delete cascade,
          name text not null,
          category text not null,
          version text not null,
          parse_status text not null check (parse_status in ('待解析', '解析中', '已解析', '需复核')),
          source text not null,
          updated_at text not null,
          storage_path text,
          file_size bigint,
          mime_type text,
          checksum text,
          created_at timestamptz not null default now()
        );

        create table if not exists document_chunks (
          id text primary key,
          project_id text not null references projects(id) on delete cascade,
          document_id text not null references project_documents(id) on delete cascade,
          chunk_index integer not null,
          content text not null,
          locator text not null,
          created_at timestamptz not null default now(),
          unique(document_id, chunk_index)
        );

        create table if not exists fact_items (
          id text primary key,
          project_id text not null references projects(id) on delete cascade,
          fact_group text not null,
          name text not null,
          value text not null,
          unit text,
          source text not null,
          owner text not null,
          status text not null check (status in ('待确认', '已确认', '已锁定', '有冲突')),
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );

        create table if not exists report_chapters (
          id text primary key,
          project_id text not null references projects(id) on delete cascade,
          chapter_no text not null,
          title text not null,
          owner text not null,
          status text not null check (status in ('未开始', '编制中', '待审核', '已审核')),
          citation_count integer not null default 0,
          quality text not null check (quality in ('阻断', '严重', '一般', '提示')),
          content text,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );

        create table if not exists quality_issues (
          id text primary key,
          project_id text not null references projects(id) on delete cascade,
          severity text not null check (severity in ('阻断', '严重', '一般', '提示')),
          type text not null,
          title text not null,
          owner text not null,
          status text not null check (status in ('待处理', '处理中', '已关闭')),
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );

        create table if not exists artifacts (
          id text primary key,
          project_id text not null references projects(id) on delete cascade,
          name text not null,
          format text not null check (format in ('Word', 'Excel', 'PPT', 'Archive')),
          status text not null check (status in ('可生成', '生成中', '已生成', '受阻')),
          updated_at text not null,
          storage_path text,
          file_size bigint,
          generated_at timestamptz,
          created_at timestamptz not null default now()
        );

        create table if not exists parse_jobs (
          id text primary key,
          document_id text references project_documents(id) on delete set null,
          status text not null default 'queued',
          message text not null,
          result jsonb not null default '{}'::jsonb,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );

        create table if not exists quality_check_jobs (
          id text primary key,
          project_id text references projects(id) on delete cascade,
          status text not null default 'queued',
          message text not null,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );

        create table if not exists audit_logs (
          id bigserial primary key,
          actor text not null default 'system',
          action text not null,
          entity_type text not null,
          entity_id text,
          detail jsonb not null default '{}'::jsonb,
          created_at timestamptz not null default now()
        );

        create table if not exists app_users (
          id text primary key,
          name text not null,
          role text not null,
          department text not null,
          status text not null check (status in ('启用', '停用')),
          email text,
          password_hash text,
          password_salt text,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );

        create table if not exists project_members (
          project_id text not null references projects(id) on delete cascade,
          user_id text not null references app_users(id) on delete cascade,
          role text not null,
          primary key (project_id, user_id)
        );

        create table if not exists auth_sessions (
          token_hash text primary key,
          user_id text not null references app_users(id) on delete cascade,
          expires_at timestamptz not null,
          created_at timestamptz not null default now()
        );

        create table if not exists report_templates (
          id text primary key,
          name text not null,
          report_type text not null,
          version text not null,
          status text not null check (status in ('草稿', '已发布', '已停用')),
          updated_at text not null,
          created_at timestamptz not null default now()
        );

        create table if not exists knowledge_items (
          id text primary key,
          title text not null,
          category text not null,
          source text not null,
          status text not null check (status in ('有效', '待复核', '停用')),
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );

        create table if not exists quality_rules (
          id text primary key,
          code text not null unique,
          name text not null,
          severity text not null check (severity in ('阻断', '严重', '一般', '提示')),
          target text not null check (target in ('fact', 'chapter', 'artifact')),
          enabled boolean not null default true,
          description text not null,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        );

        create table if not exists chapter_citations (
          id text primary key,
          chapter_id text not null references report_chapters(id) on delete cascade,
          fact_id text references fact_items(id) on delete set null,
          document_id text references project_documents(id) on delete set null,
          chunk_id text references document_chunks(id) on delete set null,
          excerpt text not null,
          source text not null,
          created_at timestamptz not null default now()
        );

        create table if not exists generated_files (
          id text primary key,
          artifact_id text references artifacts(id) on delete cascade,
          project_id text references projects(id) on delete cascade,
          name text not null,
          storage_path text not null,
          mime_type text not null,
          file_size bigint not null default 0,
          created_at timestamptz not null default now()
        );

        alter table project_documents
          add column if not exists storage_path text,
          add column if not exists file_size bigint,
          add column if not exists mime_type text,
          add column if not exists checksum text;

        alter table parse_jobs
          add column if not exists result jsonb not null default '{}'::jsonb;

        alter table artifacts
          add column if not exists storage_path text,
          add column if not exists file_size bigint,
          add column if not exists generated_at timestamptz;

        alter table app_users
          add column if not exists email text,
          add column if not exists password_hash text,
          add column if not exists password_salt text;

        alter table chapter_citations
          add column if not exists chunk_id text references document_chunks(id) on delete set null;

        create index if not exists idx_project_documents_project_id on project_documents(project_id);
        create index if not exists idx_document_chunks_project_id on document_chunks(project_id);
        create index if not exists idx_document_chunks_document_id on document_chunks(document_id);
        create index if not exists idx_fact_items_project_id on fact_items(project_id);
        create index if not exists idx_report_chapters_project_id on report_chapters(project_id);
        create index if not exists idx_quality_issues_project_id on quality_issues(project_id);
        create index if not exists idx_artifacts_project_id on artifacts(project_id);
        create index if not exists idx_project_members_project_id on project_members(project_id);
        create unique index if not exists idx_app_users_email on app_users(email) where email is not null;
        create index if not exists idx_auth_sessions_user_id on auth_sessions(user_id);
        create index if not exists idx_auth_sessions_expires_at on auth_sessions(expires_at);
        create index if not exists idx_chapter_citations_chapter_id on chapter_citations(chapter_id);
        create index if not exists idx_chapter_citations_chunk_id on chapter_citations(chunk_id);
        create index if not exists idx_generated_files_artifact_id on generated_files(artifact_id);
        create index if not exists idx_audit_logs_created_at on audit_logs(created_at desc);
        """
    )
    op.execute(
        """
        do $$
        begin
          begin
            execute 'alter table document_chunks add column if not exists embedding vector(1536)';
            execute 'create index if not exists idx_document_chunks_embedding on document_chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100)';
          exception when undefined_object or undefined_file or insufficient_privilege or feature_not_supported then
            raise notice 'pgvector embedding column/index skipped.';
          end;
        end $$;
        """
    )


def downgrade() -> None:
    op.execute("drop index if exists idx_document_chunks_embedding")
