import {
  artifacts,
  chapters,
  documents,
  facts,
  knowledgeItems,
  projects,
  qualityIssues,
  qualityRules,
  templates,
  users
} from "@zhujian/shared";
import { closePool, pool } from "../db/pool.js";
import { createPasswordRecord } from "../auth.js";

const client = await pool.connect();

try {
  await client.query("begin");
  await client.query(
    "truncate table audit_logs, auth_sessions, chapter_citations, document_chunks, quality_rules, project_members, knowledge_items, report_templates, app_users, quality_check_jobs, parse_jobs, generated_files, artifacts, quality_issues, report_chapters, fact_items, project_documents, projects restart identity cascade"
  );

  for (const user of users) {
    const password = createPasswordRecord("demo123");
    await client.query(
      "insert into app_users (id, name, role, department, status, email, password_hash, password_salt) values ($1, $2, $3, $4, $5, $6, $7, $8)",
      [user.id, user.name, user.role, user.department, user.status, user.email, password.hash, password.salt]
    );
  }

  for (const project of projects) {
    await client.query(
      "insert into projects (id, name, type, location, phase, owner, progress, risk) values ($1, $2, $3, $4, $5, $6, $7, $8)",
      [project.id, project.name, project.type, project.location, project.phase, project.owner, project.progress, project.risk]
    );
  }

  for (const project of projects) {
    for (const user of users.slice(0, 3)) {
      await client.query(
        "insert into project_members (project_id, user_id, role) values ($1, $2, $3) on conflict do nothing",
        [project.id, user.id, user.role]
      );
    }
  }

  for (const document of documents) {
    await client.query(
      "insert into project_documents (id, project_id, name, category, version, parse_status, source, updated_at) values ($1, $2, $3, $4, $5, $6, $7, $8)",
      [document.id, document.projectId, document.name, document.category, document.version, document.parseStatus, document.source, document.updatedAt]
    );
  }

  for (const fact of facts) {
    await client.query(
      "insert into fact_items (id, project_id, fact_group, name, value, unit, source, owner, status) values ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
      [fact.id, fact.projectId, fact.group, fact.name, fact.value, fact.unit ?? null, fact.source, fact.owner, fact.status]
    );
  }

  for (const chapter of chapters) {
    await client.query(
      "insert into report_chapters (id, project_id, chapter_no, title, owner, status, citation_count, quality) values ($1, $2, $3, $4, $5, $6, $7, $8)",
      [chapter.id, chapter.projectId, chapter.no, chapter.title, chapter.owner, chapter.status, chapter.citationCount, chapter.quality]
    );
  }

  for (const issue of qualityIssues) {
    await client.query(
      "insert into quality_issues (id, project_id, severity, type, title, owner, status) values ($1, $2, $3, $4, $5, $6, $7)",
      [issue.id, issue.projectId, issue.severity, issue.type, issue.title, issue.owner, issue.status]
    );
  }

  for (const artifact of artifacts) {
    await client.query(
      "insert into artifacts (id, project_id, name, format, status, updated_at) values ($1, $2, $3, $4, $5, $6)",
      [artifact.id, artifact.projectId, artifact.name, artifact.format, artifact.status, artifact.updatedAt]
    );
  }

  for (const template of templates) {
    await client.query(
      "insert into report_templates (id, name, report_type, version, status, updated_at) values ($1, $2, $3, $4, $5, $6)",
      [template.id, template.name, template.reportType, template.version, template.status, template.updatedAt]
    );
  }

  for (const item of knowledgeItems) {
    await client.query(
      "insert into knowledge_items (id, title, category, source, status) values ($1, $2, $3, $4, $5)",
      [item.id, item.title, item.category, item.source, item.status]
    );
  }

  for (const rule of qualityRules) {
    await client.query(
      "insert into quality_rules (id, code, name, severity, target, enabled, description) values ($1, $2, $3, $4, $5, $6, $7)",
      [rule.id, rule.code, rule.name, rule.severity, rule.target, rule.enabled, rule.description]
    );
  }

  await client.query(
    "insert into audit_logs (actor, action, entity_type, detail) values ($1, $2, $3, $4)",
    [
      "system",
      "seed_phase1_demo_data",
      "database",
      JSON.stringify({ projects: projects.length, documents: documents.length, facts: facts.length })
    ]
  );

  await client.query("commit");
  console.log(JSON.stringify({ ok: true, projects: projects.length, documents: documents.length, facts: facts.length, chapters: chapters.length }, null, 2));
} catch (error) {
  await client.query("rollback");
  throw error;
} finally {
  client.release();
  await closePool();
}
