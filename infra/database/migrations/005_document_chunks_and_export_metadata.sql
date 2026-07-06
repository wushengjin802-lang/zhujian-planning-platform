set search_path to public;

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

alter table chapter_citations
  add column if not exists chunk_id text references document_chunks(id) on delete set null;

create index if not exists idx_document_chunks_project_id on document_chunks(project_id);
create index if not exists idx_document_chunks_document_id on document_chunks(document_id);
create index if not exists idx_chapter_citations_chunk_id on chapter_citations(chunk_id);
