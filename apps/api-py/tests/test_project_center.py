from __future__ import annotations

from datetime import datetime, timezone
import unittest

from app.db.models import (
    AppUser,
    Artifact,
    FactItem,
    Project,
    ProjectDocument,
    ProjectMember,
    ProjectMilestone,
    QualityIssue,
    ReportChapter,
    ReportTemplate,
)
from app.services.project_center import add_default_milestones, build_project_center, map_project_profile


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

    def get(self, model, identity):
        rows = self.rows_by_model.get(model, [])
        if isinstance(identity, dict):
            return next((row for row in rows if all(getattr(row, key) == value for key, value in identity.items())), None)
        return next((row for row in rows if getattr(row, "id", None) == identity), None)

    def commit(self):
        return None


class ProjectCenterTest(unittest.TestCase):
    def test_project_center_profile_includes_members_milestones_and_initialization(self):
        now = datetime.now(timezone.utc)
        project = Project(id="P001", name="示范项目", type="可研", location="南京", phase="资料清点", owner="张工", progress=35, risk="一般")
        project.code = "ZJ-2026-0001"
        project.status = "进行中"
        project.confidentiality = "内部"
        project.template_id = "TPL-001"
        project.template_version = "v1.0"
        project.planned_start = "2026-07-01"
        project.planned_end = "2026-08-01"
        project.description = "测试项目"
        project.archived_at = None
        project.created_at = now
        project.updated_at = now

        user = AppUser(id="U1", name="张工", role="项目负责人", department="咨询部", status="启用", email="pm@example.com", password_hash=None, password_salt=None)
        member = ProjectMember(project_id="P001", user_id="U1", role="项目负责人")
        milestone = ProjectMilestone(id="PM-1", project_id="P001", name="资料清点", owner="张工", status="进行中", due_at="2026-07-10", completed_at=None, sort_order=1)
        document = ProjectDocument(id="D1", project_id="P001", name="批复.pdf", category="立项资料", version="v1", parse_status="已解析", source="上传", updated_at="2026-07-06", storage_path=None, file_size=1, mime_type="application/pdf", checksum="x")
        fact = FactItem(id="F1", project_id="P001", fact_group="基本", name="面积", value="1000", unit="㎡", source="批复", owner="张工", status="已确认")
        chapter = ReportChapter(id="C1", project_id="P001", chapter_no="1", title="总论", owner="张工", status="已审核", citation_count=3, quality="一般", content="正文")
        issue = QualityIssue(id="Q1", project_id="P001", severity="一般", type="完整性", title="补充说明", owner="张工", status="已关闭")
        artifact = Artifact(id="A1", project_id="P001", name="报告.docx", format="Word", status="已生成", updated_at="2026-07-06", storage_path=None, file_size=None, generated_at=None)
        template = ReportTemplate(id="TPL-001", name="可研模板", report_type="可研", version="v1.0", status="已发布", updated_at="2026-07-06")

        db = FakeSession({
            Project: [project],
            AppUser: [user],
            ProjectMember: [member],
            ProjectMilestone: [milestone],
            ProjectDocument: [document],
            FactItem: [fact],
            ReportChapter: [chapter],
            QualityIssue: [issue],
            Artifact: [artifact],
            ReportTemplate: [template],
        })
        result = build_project_center(db, {"id": "U1", "name": "张工", "role": "项目负责人", "department": "咨询部", "status": "启用"})
        self.assertEqual(result["metrics"][0]["value"], 1)
        self.assertTrue(result["capabilities"]["projectWizard"])
        self.assertEqual(result["projects"][0]["code"], "ZJ-2026-0001")
        self.assertTrue(result["projects"][0]["initialization"]["ready"])

        profile = map_project_profile(db, project, {"id": "U1", "name": "张工", "role": "项目负责人", "department": "咨询部", "status": "启用"})
        self.assertEqual(profile["members"][0]["name"], "张工")
        self.assertEqual(profile["milestones"][0]["name"], "资料清点")
        self.assertTrue(profile["actions"]["canClose"])

    def test_default_milestones_are_created_once(self):
        project = Project(id="P002", name="新项目", type="可研", location="南京", phase="项目建档", owner="张工", progress=8, risk="一般")
        project.code = "ZJ-2026-0002"
        project.status = "建档中"
        project.confidentiality = "内部"
        project.template_id = None
        project.template_version = None
        project.planned_start = None
        project.planned_end = None
        project.description = None
        project.archived_at = None
        db = FakeSession({Project: [project], ProjectMilestone: []})
        first = add_default_milestones(db, project)
        second = add_default_milestones(db, project)
        self.assertEqual(len(first), 5)
        self.assertEqual(len(second), 5)
        self.assertEqual(len(db.rows_by_model[ProjectMilestone]), 5)


if __name__ == "__main__":
    unittest.main()
