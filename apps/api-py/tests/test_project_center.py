from __future__ import annotations

from datetime import datetime, timezone
import unittest

from app.db.models import (
    AppUser,
    Artifact,
    FactItem,
    Project,
    ProjectDocument,
    ProjectInitializationRecord,
    ProjectMaterialRequirement,
    ProjectMember,
    ProjectMilestone,
    ProjectRegionRule,
    ProjectRuleMigrationPlan,
    ProjectRevision,
    ProjectWizardDraft,
    QualityCheckJob,
    QualityIssue,
    ReportChapter,
    ReportTemplate,
)
from app.services.project_center import add_default_milestones, apply_rule_migration_plan, build_project_center, create_project_revision, create_rule_migration_plan, evaluate_project_status_gate, ensure_project_initialization_package, map_project_profile, preview_project_rule_migration


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
        milestone = ProjectMilestone(id="PM-1", project_id="P001", name="资料清点", owner="张工", status="已完成", due_at="2026-07-10", completed_at=now, sort_order=1)
        material = ProjectMaterialRequirement(id="PMR-1", project_id="P001", category="立项资料", name="项目立项批复或任务来源说明", required=True, status="已确认", source_type="document", source_id="D1", sort_order=1)
        record = ProjectInitializationRecord(id="PIR-1", project_id="P001", package_version="v2.1", status="已初始化", summary={"created": {}}, created_by="张工", created_at=now, updated_at=now)
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
            ProjectMaterialRequirement: [material],
            ProjectInitializationRecord: [record],
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

    def test_initialization_package_creates_material_fact_chapter_and_artifact_plan(self):
        project = Project(id="P003", name="初始化项目", type="可研", location="南京", phase="项目建档", owner="张工", progress=8, risk="一般")
        project.code = "ZJ-2026-0003"
        project.status = "建档中"
        project.confidentiality = "内部"
        project.template_id = "TPL-001"
        project.template_version = "v1.0"
        project.planned_start = None
        project.planned_end = None
        project.description = None
        project.archived_at = None
        db = FakeSession({Project: [project], ProjectMember: [], ProjectMilestone: [], ProjectMaterialRequirement: [], ProjectInitializationRecord: [], FactItem: [], ReportChapter: [], Artifact: []})
        summary = ensure_project_initialization_package(db, project, {"id": "U1", "name": "张工", "role": "项目负责人"})
        self.assertEqual(summary["packageVersion"], "v2.3")
        self.assertGreaterEqual(len(db.rows_by_model[ProjectMaterialRequirement]), 5)
        self.assertGreaterEqual(len(db.rows_by_model[FactItem]), 5)
        self.assertGreaterEqual(len(db.rows_by_model[ReportChapter]), 6)
        self.assertGreaterEqual(len(db.rows_by_model[Artifact]), 4)
        profile = map_project_profile(db, project, {"id": "U1", "name": "张工", "role": "项目负责人"})
        self.assertTrue(profile["initialization"]["packageReady"])

    def test_archive_gate_blocks_until_chapters_and_artifacts_are_ready(self):
        now = datetime.now(timezone.utc)
        project = Project(id="P004", name="待归档项目", type="可研", location="南京", phase="项目关闭", owner="张工", progress=90, risk="一般")
        project.code = "ZJ-2026-0004"
        project.status = "已关闭"
        project.confidentiality = "内部"
        project.template_id = "TPL-001"
        project.template_version = "v1.0"
        project.planned_start = None
        project.planned_end = None
        project.description = None
        project.archived_at = None
        member = ProjectMember(project_id="P004", user_id="U1", role="项目负责人")
        milestone = ProjectMilestone(id="PM-4", project_id="P004", name="成果归档", owner="张工", status="已完成", due_at=None, completed_at=now, sort_order=1)
        material = ProjectMaterialRequirement(id="PMR-4", project_id="P004", category="立项资料", name="项目立项批复或任务来源说明", required=True, status="已确认", source_type=None, source_id=None, sort_order=1)
        fact = FactItem(id="F4", project_id="P004", fact_group="基本", name="建设地点", value="南京", unit=None, source="人工", owner="张工", status="已确认")
        chapter = ReportChapter(id="C4", project_id="P004", chapter_no="1", title="项目概况", owner="张工", status="待审核", citation_count=1, quality="提示", content="草稿")
        artifact = Artifact(id="A4", project_id="P004", name="成果报告.docx", format="Word", status="可生成", updated_at="2026-07-06", storage_path=None, file_size=None, generated_at=None)
        db = FakeSession({Project: [project], ProjectMember: [member], ProjectMilestone: [milestone], ProjectMaterialRequirement: [material], ProjectInitializationRecord: [], FactItem: [fact], ReportChapter: [chapter], Artifact: [artifact], QualityIssue: [], ProjectDocument: [], QualityCheckJob: []})
        gate = evaluate_project_status_gate(db, project, "已归档")
        self.assertFalse(gate["allowed"])
        self.assertTrue(any(item["code"] == "unapproved_chapters" for item in gate["blockers"]))
        self.assertTrue(any(item["code"] == "ungenerated_artifacts" for item in gate["blockers"]))

    def test_region_rule_drives_initialization_package(self):
        project = Project(id="P005", name="规则项目", type="政府投资", location="南京", phase="项目建档", owner="张工", progress=8, risk="一般")
        project.code = "ZJ-2026-0005"
        project.status = "建档中"
        project.confidentiality = "内部"
        project.template_id = "TPL-001"
        project.template_version = "v1.0"
        project.region = "江苏"
        project.region_rule_id = "BUILTIN-GOV-INVESTMENT"
        project.initialization_rule_version = None
        project.draft_source_id = None
        project.planned_start = None
        project.planned_end = None
        project.description = None
        project.archived_at = None
        db = FakeSession({Project: [project], ProjectRegionRule: [], ProjectMember: [], ProjectMilestone: [], ProjectMaterialRequirement: [], ProjectInitializationRecord: [], FactItem: [], ReportChapter: [], Artifact: []})
        summary = ensure_project_initialization_package(db, project, {"id": "U1", "name": "张工", "role": "项目负责人"})
        self.assertEqual(summary["ruleId"], "BUILTIN-GOV-INVESTMENT")
        self.assertTrue(any(row.name == "政府投资合规清单.xlsx" for row in db.rows_by_model[Artifact]))
        self.assertTrue(any(row.name == "财政资金比例" for row in db.rows_by_model[FactItem]))

    def test_project_center_lists_region_rules_and_drafts(self):
        now = datetime.now(timezone.utc)
        user = AppUser(id="U1", name="张工", role="项目负责人", department="咨询部", status="启用", email="pm@example.com", password_hash=None, password_salt=None)
        draft = ProjectWizardDraft(id="PWD-1", user_id="U1", name="草稿项目", step=1, status="草稿", payload={"name": "草稿项目", "regionRuleId": "BUILTIN-COMMON"}, created_at=now, updated_at=now)
        db = FakeSession({Project: [], AppUser: [user], ProjectWizardDraft: [draft], ProjectRegionRule: [], ReportTemplate: []})
        result = build_project_center(db, {"id": "U1", "name": "张工", "role": "项目负责人", "department": "咨询部", "status": "启用"})
        self.assertGreaterEqual(len(result["regionRules"]), 1)
        self.assertEqual(result["wizardDrafts"][0]["id"], "PWD-1")
        self.assertTrue(result["capabilities"]["wizardDraft"])

    def test_migration_preview_and_plan_detect_rule_differences(self):
        now = datetime.now(timezone.utc)
        project = Project(id="P006", name="迁移项目", type="可研", location="南京", phase="项目建档", owner="张工", progress=20, risk="一般")
        project.code = "ZJ-2026-0006"
        project.status = "进行中"
        project.confidentiality = "内部"
        project.template_id = "TPL-OLD"
        project.template_version = "v1.0"
        project.region = "全国"
        project.region_rule_id = "BUILTIN-COMMON"
        project.initialization_rule_version = "v2.2"
        project.draft_source_id = None
        project.planned_start = None
        project.planned_end = None
        project.description = None
        project.archived_at = None
        project.created_at = now
        project.updated_at = now
        material = ProjectMaterialRequirement(id="PMR-6", project_id="P006", category="立项资料", name="项目立项批复或任务来源说明", required=True, status="待上传", source_type=None, source_id=None, sort_order=1)
        db = FakeSession({Project: [project], ProjectMaterialRequirement: [material], ProjectRegionRule: [], ProjectRuleMigrationPlan: [], ProjectMember: [], ProjectMilestone: [], ProjectInitializationRecord: [], FactItem: [], ReportChapter: [], Artifact: []})
        preview = preview_project_rule_migration(db, project, "TPL-NEW", "v2.0", "BUILTIN-GOV-INVESTMENT")
        self.assertTrue(preview["templateChanged"])
        self.assertTrue(preview["ruleChanged"])
        self.assertGreater(preview["impactCount"], 0)
        plan = create_rule_migration_plan(db, project, {"id": "U1", "name": "张工"}, "TPL-NEW", "v2.0", "BUILTIN-GOV-INVESTMENT")
        self.assertEqual(plan.status, "待应用")
        apply_rule_migration_plan(db, project, plan, {"id": "U1", "name": "张工"})
        self.assertEqual(plan.status, "已应用")
        self.assertEqual(project.template_id, "TPL-NEW")
        self.assertEqual(project.region_rule_id, "BUILTIN-GOV-INVESTMENT")

    def test_project_revision_chain_creates_single_draft_revision(self):
        now = datetime.now(timezone.utc)
        project = Project(id="P007", name="修订项目", type="可研", location="南京", phase="项目关闭", owner="张工", progress=95, risk="一般")
        project.code = "ZJ-2026-0007"
        project.status = "已关闭"
        project.confidentiality = "内部"
        project.template_id = "TPL-001"
        project.template_version = "v1.0"
        project.region = "全国"
        project.region_rule_id = "BUILTIN-COMMON"
        project.initialization_rule_version = "v2.3"
        project.draft_source_id = None
        project.planned_start = None
        project.planned_end = None
        project.description = None
        project.archived_at = None
        project.created_at = now
        project.updated_at = now
        db = FakeSession({Project: [project], ProjectRevision: [], ProjectMember: [], ProjectMilestone: [], ProjectMaterialRequirement: [], ProjectInitializationRecord: [], FactItem: [], ReportChapter: [], Artifact: [], QualityIssue: [], ProjectDocument: [], QualityCheckJob: []})
        rev1 = create_project_revision(db, project, {"id": "U1", "name": "张工"}, "第一次修订", "范围调整")
        rev2 = create_project_revision(db, project, {"id": "U1", "name": "张工"}, "重复创建", "应复用草稿")
        self.assertEqual(rev1.id, rev2.id)
        self.assertEqual(rev1.revision_no, "R001")
        self.assertIn("project", rev1.baseline_snapshot)


if __name__ == "__main__":
    unittest.main()
