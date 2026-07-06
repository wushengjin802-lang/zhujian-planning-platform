set search_path to public;

alter table app_users
  add column if not exists email text,
  add column if not exists password_hash text,
  add column if not exists password_salt text;

create unique index if not exists idx_app_users_email on app_users(email) where email is not null;

create table if not exists auth_sessions (
  token_hash text primary key,
  user_id text not null references app_users(id) on delete cascade,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_auth_sessions_user_id on auth_sessions(user_id);
create index if not exists idx_auth_sessions_expires_at on auth_sessions(expires_at);

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
  excerpt text not null,
  source text not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_chapter_citations_chapter_id on chapter_citations(chapter_id);
