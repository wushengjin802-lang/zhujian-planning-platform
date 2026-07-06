set search_path to public;

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
  created_at timestamptz not null default now()
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
  created_at timestamptz not null default now()
);

create table if not exists parse_jobs (
  id text primary key,
  document_id text references project_documents(id) on delete set null,
  status text not null default 'queued',
  message text not null,
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

create index if not exists idx_project_documents_project_id on project_documents(project_id);
create index if not exists idx_fact_items_project_id on fact_items(project_id);
create index if not exists idx_report_chapters_project_id on report_chapters(project_id);
create index if not exists idx_quality_issues_project_id on quality_issues(project_id);
create index if not exists idx_artifacts_project_id on artifacts(project_id);
