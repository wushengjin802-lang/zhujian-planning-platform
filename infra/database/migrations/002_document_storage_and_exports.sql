set search_path to public;

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

create index if not exists idx_generated_files_artifact_id on generated_files(artifact_id);
