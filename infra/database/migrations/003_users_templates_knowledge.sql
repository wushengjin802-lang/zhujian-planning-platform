set search_path to public;

create table if not exists app_users (
  id text primary key,
  name text not null,
  role text not null,
  department text not null,
  status text not null check (status in ('启用', '停用')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists project_members (
  project_id text not null references projects(id) on delete cascade,
  user_id text not null references app_users(id) on delete cascade,
  role text not null,
  primary key (project_id, user_id)
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

create index if not exists idx_project_members_project_id on project_members(project_id);
create index if not exists idx_audit_logs_created_at on audit_logs(created_at desc);
