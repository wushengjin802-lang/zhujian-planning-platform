from __future__ import annotations

from datetime import datetime, timezone
import unittest

from app.db.models import (
    Artifact,
    AuditLog,
    FactItem,
    InvestmentEstimate,
    ParseJob,
    Project,
    ProjectDocument,
    QualityCheckJob,
    QualityIssue,
    ReportChapter,
    WorkItem,
    ReviewTask,
    Notification,
    AppUser,
)
from app.services.dashboard import build_dashboard


class ScalarRows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class FakeSession:
    def __init__(self, rows_by_model):
        self.rows_by_model = rows_by_model

    def scalars(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        return ScalarRows(self.rows_by_model.get(entity, []))

    def scalar(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        rows = self.rows_by_model.get(entity, [])
        return rows[0] if rows else None

    def add(self, row):
        self.rows_by_model.setdefault(type(row), []).append(row)

    def commit(self):
        return None


class DashboardAggregationTest(unittest.TestCase):
    def test_build_dashboard_aggregates_work_and_risk(self):
        now = datetime.now(timezone.utc)
        project = Project(id="P001", name="示范项目", type="可研", location="南京", phase="章节编制", owner="张工", progress=48, risk="严重")
        project.created_at = now
        project.updated_at = now

        document = ProjectDocument(
            id="D001", project_id="P001", name="立项批复.pdf", category="立项资料", version="v1.0",
            parse_status="待解析", source="上传", updated_at="2026-07-03", storage_path=None,
            file_size=100, mime_type="application/pdf", checksum="abc"
        )
        document.created_at = now

        fact = FactItem(id="F001", project_id="P001", fact_group="建设规模", name="总建筑面积", value="30000", unit="㎡", source="立项批复", owner="李工", status="有冲突")
        chapter = ReportChapter(id="C001", project_id="P001", chapter_no="1", title="总论", owner="王工", status="待审核", citation_count=2, quality="严重", content="正文")
        issue = QualityIssue(id="Q001", project_id="P001", severity="阻断", type="发布门禁", title="章节未审核", owner="审核人", status="待处理")
        artifact = Artifact(id="A001", project_id="P001", name="可研报告.docx", format="Word", status="生成中", updated_at="2026-07-03", storage_path=None, file_size=None, generated_at=None)
        estimate = InvestmentEstimate(id="E001", project_id="P001", status="calculated", input_snapshot={}, output={}, sensitivity={}, confirmed_by=None, confirmed_at=None)
        estimate.created_at = now
        estimate.updated_at = now

        parse_job = ParseJob(id="JOB-1", document_id="D001", status="queued", message="排队中", result={})
        parse_job.created_at = now
        parse_job.updated_at = now
        quality_job = QualityCheckJob(id="QC-1", project_id="P001", status="completed", message="完成")
        quality_job.created_at = now
        quality_job.updated_at = now
        audit = AuditLog(id=1, actor="张工", action="upload_document", entity_type="project_document", entity_id="D001", detail={})
        audit.created_at = now

        db = FakeSession({
            Project: [project],
            ProjectDocument: [document],
            FactItem: [fact],
            ReportChapter: [chapter],
            QualityIssue: [issue],
            Artifact: [artifact],
            InvestmentEstimate: [estimate],
            ParseJob: [parse_job],
            QualityCheckJob: [quality_job],
            AuditLog: [audit],
            WorkItem: [],
            ReviewTask: [],
            Notification: [],
            AppUser: [],
        })

        result = build_dashboard(db, {"id": "U1", "name": "项目负责人", "role": "项目负责人", "department": "咨询部", "status": "启用"}, "P001")

        self.assertEqual(result["scope"], "project")
        self.assertEqual(result["roleMode"], "management")
        self.assertGreaterEqual(len(result["workItems"]), 2)
        self.assertEqual(len(result["reviewQueue"]), 2)
        self.assertTrue(any(item["priority"] == "P0" for item in result["workItems"]))
        self.assertTrue(any(item["status"] == "运行中" for item in result["tasks"]))
        self.assertTrue(result["capabilities"]["persistentWorkItems"])
        self.assertTrue(any(item.get("persistent") for item in result["workItems"]))
        blocker_metric = next(item for item in result["metrics"] if item["key"] == "blockingIssues")
        self.assertEqual(blocker_metric["value"], 1)
        self.assertEqual(result["workflow"][0]["percentage"], 0)


if __name__ == "__main__":
    unittest.main()
