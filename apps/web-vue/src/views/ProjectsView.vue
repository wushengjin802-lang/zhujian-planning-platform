<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { usePlatformStore } from "../stores/platform";
import {
  addProjectMember,
  addProjectMilestone,
  approveProjectMigrationPlan,
  changeProjectStatus,
  createProjectMigrationPlan,
  createProjectRevision,
  closeProjectRevision,
  initializeProjectPackage,
  loadProjectMigrationPreview,
  applyProjectMigrationPlan,
  rejectProjectMigrationPlan,
  rollbackProjectMigrationPlan,
  copyProject,
  createProject,
  loadProjectCenter,
  loadProjectProfile,
  loadProjectStatusGate,
  saveProjectDraft,
  deleteProjectDraft,
  removeProjectMember,
  updateProject,
  updateProjectMaterial,
  updateProjectMilestone
} from "../api/client";
import type { ProjectCenterPayload, ProjectCreateInput, ProjectMilestoneInfo, ProjectProfile, ProjectSummary } from "../types";

const store = usePlatformStore();
const loading = ref(false);
const center = ref<ProjectCenterPayload | null>(null);
const profile = ref<ProjectProfile | null>(null);
const drawerOpen = ref(false);
const activeTab = ref("profile");
const wizardStep = ref(0);
const currentDraftId = ref<string | undefined>();

const filters = reactive({ keyword: "", status: "", risk: "" });
const memberForm = reactive({ userId: "", role: "项目成员" });
const milestoneForm = reactive({ name: "", owner: "项目负责人", status: "未开始", dueAt: "" });
const copyForm = reactive({ open: false, name: "", copyMembers: true, copyMilestones: true, copySettings: true });
const migrationForm = reactive({ templateId: "", templateVersion: "", regionRuleId: "" });
const revisionForm = reactive({ title: "", reason: "" });
const materialStatuses = ["待上传", "已上传", "已确认", "不适用"];
const form = reactive<ProjectCreateInput & { open: boolean }>({
  open: false,
  name: "新建可研样本项目",
  type: "可行性研究报告",
  location: "待补充",
  owner: "项目负责人",
  confidentiality: "内部",
  templateId: "",
  templateVersion: "",
  region: "全国",
  regionRuleId: "BUILTIN-COMMON",
  plannedStart: "",
  plannedEnd: "",
  description: "",
  members: [],
  milestones: [
    { name: "资料清点", owner: "资料负责人", status: "未开始", sortOrder: 1 },
    { name: "事实确认", owner: "咨询负责人", status: "未开始", sortOrder: 2 },
    { name: "章节编制", owner: "报告负责人", status: "未开始", sortOrder: 3 },
    { name: "质量审核", owner: "审核负责人", status: "未开始", sortOrder: 4 },
    { name: "成果归档", owner: "项目负责人", status: "未开始", sortOrder: 5 }
  ]
});

const filteredProjects = computed(() => {
  const keyword = filters.keyword.trim().toLowerCase();
  return (center.value?.projects ?? []).filter((item) => {
    const text = `${item.code ?? ""} ${item.name} ${item.location} ${item.owner}`.toLowerCase();
    return (!keyword || text.includes(keyword)) && (!filters.status || item.status === filters.status) && (!filters.risk || item.risk === filters.risk);
  });
});

const selectedSummary = computed(() => center.value?.projects.find((item) => item.id === profile.value?.id));
const templateOptions = computed(() => center.value?.templates ?? []);
const userOptions = computed(() => center.value?.users ?? []);
const regionRuleOptions = computed(() => center.value?.regionRules ?? []);
const draftOptions = computed(() => center.value?.wizardDrafts ?? []);

const projectStageSteps = [
  { no: 1, title: "项目建档", subtitle: "范围与权限" },
  { no: 2, title: "资料清点", subtitle: "版本与完整性" },
  { no: 3, title: "事实确认", subtitle: "统一数据底板" },
  { no: 4, title: "章节编制", subtitle: "初稿与引用" },
  { no: 5, title: "分析测算", subtitle: "GIS与投资" },
  { no: 6, title: "专业复核", subtitle: "会签与门禁" },
  { no: 7, title: "成果输出", subtitle: "发布与归档" }
];

const activeStageNo = computed(() => 1);

const overviewMetricMeta: Record<string, { icon: string; color: string; order: number }> = {
  total: { icon: "项", color: "#20a681", order: 1 },
  active: { icon: "进", color: "#4a90ff", order: 2 },
  notInitialized: { icon: "初", color: "#f5a623", order: 3 },
  risk: { icon: "险", color: "#f05b5b", order: 4 },
  gateBlocked: { icon: "禁", color: "#67c23a", order: 5 },
  archived: { icon: "归", color: "#8b99aa", order: 6 }
};

const compactOverviewMetrics = computed(() => {
  const metrics = center.value?.metrics ?? [];
  return metrics
    .filter((metric) => Object.prototype.hasOwnProperty.call(overviewMetricMeta, metric.key))
    .sort((a, b) => overviewMetricMeta[a.key].order - overviewMetricMeta[b.key].order)
    .map((metric) => ({ ...metric, ...overviewMetricMeta[metric.key] }));
});

function riskTag(risk?: string) {
  if (risk === "阻断") return "danger";
  if (risk === "严重") return "warning";
  if (risk === "提示") return "info";
  return "success";
}

function statusTag(status?: string) {
  if (status === "已归档") return "info";
  if (status === "已关闭") return "warning";
  if (status === "建档中") return "primary";
  return "success";
}

function statText(value: number, total: number) {
  return `${value}/${total}`;
}

function gateType(allowed?: boolean) {
  return allowed ? "success" : "danger";
}

function gateSummary(blockers?: Array<{ message: string }>, warnings?: Array<{ message: string }>) {
  const blockText = blockers?.map((item) => item.message).join("；") || "无阻断";
  const warnText = warnings?.length ? `；提醒：${warnings.map((item) => item.message).join("；")}` : "";
  return `${blockText}${warnText}`;
}

function materialStatusType(status?: string) {
  if (status === "已确认") return "success";
  if (status === "已上传") return "primary";
  if (status === "不适用") return "info";
  return "warning";
}

async function reload(selectId?: string) {
  loading.value = true;
  try {
    center.value = await loadProjectCenter();
    const targetId = selectId || profile.value?.id || store.currentProject?.id || center.value.projects[0]?.id;
    if (targetId) await selectProject(targetId, false);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "项目中心加载失败");
  } finally {
    loading.value = false;
  }
}

async function selectProject(projectId: string, openDrawer = true) {
  profile.value = await loadProjectProfile(projectId);
  syncMigrationFormFromProfile();
  store.currentProjectId = projectId;
  if (openDrawer) drawerOpen.value = true;
}

function resetWizard() {
  wizardStep.value = 0;
  form.open = true;
  form.name = "新建可研样本项目";
  form.type = "可行性研究报告";
  form.location = "待补充";
  form.owner = store.currentUser?.name || "项目负责人";
  form.confidentiality = "内部";
  form.templateId = templateOptions.value[0]?.id || "";
  form.templateVersion = templateOptions.value[0]?.version || "";
  form.region = "全国";
  form.regionRuleId = regionRuleOptions.value[0]?.id || "BUILTIN-COMMON";
  currentDraftId.value = undefined;
  form.plannedStart = "";
  form.plannedEnd = "";
  form.description = "";
  form.members = [];
}

function bindSelectedTemplate() {
  const tpl = templateOptions.value.find((item) => item.id === form.templateId);
  form.templateVersion = tpl?.version || "";
}

function bindSelectedRegionRule() {
  const rule = regionRuleOptions.value.find((item) => item.id === form.regionRuleId);
  form.region = rule?.region || form.region || "全国";
}

async function saveWizardDraft() {
  const draft = await saveProjectDraft({ id: currentDraftId.value, name: form.name || "未命名项目草稿", step: wizardStep.value, payload: { ...form, open: undefined } as ProjectCreateInput });
  currentDraftId.value = draft.id;
  await reload();
  form.open = true;
  ElMessage.success("建档草稿已保存");
}

function loadWizardDraft(draftId: string) {
  const draft = draftOptions.value.find((item) => item.id === draftId);
  if (!draft) return;
  Object.assign(form, { ...draft.payload, open: true });
  currentDraftId.value = draft.id;
  wizardStep.value = draft.step || 0;
  ElMessage.success("已载入建档草稿");
}

async function removeWizardDraft(draftId: string) {
  await deleteProjectDraft(draftId);
  await reload();
  ElMessage.success("建档草稿已删除");
}

function addWizardMember() {
  if (!memberForm.userId) return;
  form.members = [...(form.members ?? []), { userId: memberForm.userId, role: memberForm.role }];
  memberForm.userId = "";
  memberForm.role = "项目成员";
}

async function submitWizard() {
  if (!form.name?.trim()) {
    ElMessage.warning("请输入项目名称");
    return;
  }
  const created = await createProject({ ...form, draftId: currentDraftId.value });
  form.open = false;
  await store.refresh();
  await reload(created.id);
  ElMessage.success("项目已创建并完成初始化");
}

async function saveProfile() {
  if (!profile.value) return;
  await updateProject(profile.value.id, {
    name: profile.value.name,
    type: profile.value.type,
    location: profile.value.location,
    owner: profile.value.owner,
    phase: profile.value.phase,
    progress: profile.value.progress,
    risk: profile.value.risk,
    confidentiality: profile.value.confidentiality || "内部",
    templateId: profile.value.templateId || undefined,
    templateVersion: profile.value.templateVersion || undefined,
    region: profile.value.region || undefined,
    regionRuleId: profile.value.regionRuleId || undefined,
    plannedStart: profile.value.plannedStart || undefined,
    plannedEnd: profile.value.plannedEnd || undefined,
    description: profile.value.description || undefined
  });
  await store.refresh();
  await reload(profile.value.id);
  ElMessage.success("项目信息已保存");
}

function syncMigrationFormFromProfile() {
  if (!profile.value) return;
  migrationForm.templateId = profile.value.templateId || "";
  migrationForm.templateVersion = profile.value.templateVersion || "";
  migrationForm.regionRuleId = profile.value.regionRuleId || "";
}

async function previewMigration() {
  if (!profile.value) return;
  const preview = await loadProjectMigrationPreview(profile.value.id, { ...migrationForm });
  profile.value.migrationPreview = preview;
  ElMessage({ type: preview.impactCount ? "warning" : "success", message: `迁移影响项：${preview.impactCount}，风险：${preview.riskLevel}` });
}

async function createMigrationPlan() {
  if (!profile.value) return;
  await createProjectMigrationPlan(profile.value.id, { ...migrationForm });
  await reload(profile.value.id);
  ElMessage.success("迁移计划已生成");
}

async function approveMigrationPlan(planId: string) {
  if (!profile.value) return;
  const { value } = await ElMessageBox.prompt("请输入审批意见，可留空", "审批迁移计划", { confirmButtonText: "通过", cancelButtonText: "取消", inputPlaceholder: "审批意见" });
  await approveProjectMigrationPlan(profile.value.id, planId, value);
  await reload(profile.value.id);
  ElMessage.success("迁移计划已审批通过");
}

async function rejectMigrationPlan(planId: string) {
  if (!profile.value) return;
  const { value } = await ElMessageBox.prompt("请输入驳回原因", "驳回迁移计划", { confirmButtonText: "驳回", cancelButtonText: "取消", inputPlaceholder: "驳回原因" });
  await rejectProjectMigrationPlan(profile.value.id, planId, value);
  await reload(profile.value.id);
  ElMessage.success("迁移计划已驳回");
}

async function applyMigrationPlan(planId: string) {
  if (!profile.value) return;
  await ElMessageBox.confirm("应用迁移计划会更新项目模板/地区规则并补齐初始化包，不会删除现有资料、事实、章节和成果项。确认应用？", "应用迁移计划", { type: "warning" });
  await applyProjectMigrationPlan(profile.value.id, planId);
  await reload(profile.value.id);
  ElMessage.success("迁移计划已应用");
}

async function rollbackMigrationPlan(planId: string) {
  if (!profile.value) return;
  const { value } = await ElMessageBox.prompt("回滚只恢复模板/地区规则指针，不删除迁移期间补齐的项目骨架。请输入回滚说明，可留空。", "回滚迁移计划", { confirmButtonText: "回滚", cancelButtonText: "取消", inputPlaceholder: "回滚说明" });
  await rollbackProjectMigrationPlan(profile.value.id, planId, value);
  await reload(profile.value.id);
  ElMessage.success("迁移计划已回滚");
}

async function createRevision() {
  if (!profile.value) return;
  await createProjectRevision(profile.value.id, { title: revisionForm.title || `${profile.value.name} 修订`, reason: revisionForm.reason });
  revisionForm.title = "";
  revisionForm.reason = "";
  await reload(profile.value.id);
  ElMessage.success("项目修订已创建");
}

async function closeRevision(revisionId: string) {
  if (!profile.value) return;
  await closeProjectRevision(profile.value.id, revisionId, "已确认");
  await reload(profile.value.id);
  ElMessage.success("项目修订已确认关闭");
}

async function addMemberToProfile() {
  if (!profile.value || !memberForm.userId) return;
  await addProjectMember(profile.value.id, { userId: memberForm.userId, role: memberForm.role });
  memberForm.userId = "";
  memberForm.role = "项目成员";
  await reload(profile.value.id);
}

async function removeMember(userId: string) {
  if (!profile.value) return;
  await ElMessageBox.confirm("确认移除该项目成员？", "移除成员", { type: "warning" });
  await removeProjectMember(profile.value.id, userId);
  await reload(profile.value.id);
}

async function addMilestoneToProfile() {
  if (!profile.value || !milestoneForm.name) return;
  await addProjectMilestone(profile.value.id, { ...milestoneForm });
  milestoneForm.name = "";
  milestoneForm.owner = "项目负责人";
  milestoneForm.status = "未开始";
  milestoneForm.dueAt = "";
  await reload(profile.value.id);
}

async function saveMilestone(item: ProjectMilestoneInfo) {
  if (!profile.value) return;
  await updateProjectMilestone(profile.value.id, item.id, { name: item.name, owner: item.owner, status: item.status, dueAt: item.dueAt || undefined, sortOrder: item.sortOrder });
  await reload(profile.value.id);
}

async function initializePackage() {
  if (!profile.value) return;
  const updated = await initializeProjectPackage(profile.value.id);
  profile.value = updated;
  await store.refresh();
  await reload(updated.id);
  ElMessage.success("项目初始化包已生成/补齐");
}

async function saveMaterial(item: { id: string; status: string; sourceType?: string | null; sourceId?: string | null }) {
  if (!profile.value) return;
  await updateProjectMaterial(profile.value.id, item.id, { status: item.status, sourceType: item.sourceType || undefined, sourceId: item.sourceId || undefined });
  await reload(profile.value.id);
  ElMessage.success("资料清单状态已更新");
}

async function previewGate(targetStatus: string) {
  if (!profile.value) return;
  const gate = await loadProjectStatusGate(profile.value.id, targetStatus);
  ElMessage({ type: gate.allowed ? "success" : "warning", message: `${targetStatus}门禁：${gateSummary(gate.blockers, gate.warnings)}` });
}

async function setStatus(status: string) {
  if (!profile.value) return;
  try {
    await changeProjectStatus(profile.value.id, status, `项目中心变更为${status}`);
    await store.refresh();
    await reload(profile.value.id);
    ElMessage.success(`项目已变更为${status}`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "项目状态门禁未通过");
  }
}

function openCopyDialog() {
  if (!profile.value) return;
  copyForm.open = true;
  copyForm.name = `${profile.value.name}-复制`;
}

async function submitCopy() {
  if (!profile.value) return;
  const copied = await copyProject(profile.value.id, { name: copyForm.name, copyMembers: copyForm.copyMembers, copyMilestones: copyForm.copyMilestones, copySettings: copyForm.copySettings });
  copyForm.open = false;
  await store.refresh();
  await reload(copied.id);
}

onMounted(() => reload());
</script>

<template>
  <div class="toolbar">
    <div>
      <strong>项目中心</strong>
      <p style="margin: 4px 0 0; color: #6b7c88">建档、成员、里程碑、模板、密级与状态流转</p>
    </div>
    <div class="topbar-actions">
      <el-button @click="reload()">刷新</el-button>
      <el-button type="primary" @click="resetWizard">新建项目</el-button>
    </div>
  </div>

  <div v-loading="loading">
    <el-card class="project-stage-card" shadow="never">
      <div class="project-stage-flow">
        <div v-for="step in projectStageSteps" :key="step.no" class="project-stage-item" :class="{ active: step.no === activeStageNo, passed: step.no < activeStageNo }">
          <div class="stage-index">{{ step.no }}</div>
          <div class="stage-title">{{ step.title }}</div>
          <div class="stage-subtitle">{{ step.subtitle }}</div>
        </div>
      </div>
    </el-card>

    <el-card class="overview-panel compact-overview" shadow="never">
      <div class="overview-title">项目概览 <span>（所有项目）</span></div>
      <div class="overview-metric-row">
        <div v-for="metric in compactOverviewMetrics" :key="metric.key" class="overview-metric-card">
          <div class="overview-metric-text">
            <span>{{ metric.label }}</span>
            <strong>{{ metric.value }}</strong>
          </div>
          <div class="overview-icon" :style="{ color: metric.color, background: `${metric.color}18` }">{{ metric.icon }}</div>
        </div>
      </div>
    </el-card>

    <el-card class="panel" shadow="never" style="margin-bottom: 16px">
      <div class="toolbar" style="margin-bottom: 0">
        <el-input v-model="filters.keyword" clearable placeholder="搜索编号、名称、地点、负责人" style="width: 320px" />
        <div class="topbar-actions">
          <el-select v-model="filters.status" clearable placeholder="项目状态" style="width: 140px">
            <el-option v-for="status in center?.statuses ?? []" :key="status" :label="status" :value="status" />
          </el-select>
          <el-select v-model="filters.risk" clearable placeholder="风险等级" style="width: 140px">
            <el-option v-for="risk in ['阻断', '严重', '一般', '提示']" :key="risk" :label="risk" :value="risk" />
          </el-select>
        </div>
      </div>
    </el-card>

    <el-row :gutter="16">
      <el-col v-for="project in filteredProjects" :key="project.id" :xs="24" :md="12" :lg="8">
        <el-card class="panel" shadow="never" @click="selectProject(project.id)">
          <div class="panel-title">
            <h2>{{ project.name }}</h2>
            <div class="topbar-actions">
              <el-tag :type="statusTag(project.status)">{{ project.status }}</el-tag>
              <el-tag :type="riskTag(project.risk)">{{ project.risk }}</el-tag>
            </div>
          </div>
          <p>{{ project.code }} · {{ project.location }} · {{ project.type }}</p>
          <el-progress :percentage="project.progress" />
          <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 12px 0">
            <small>资料 {{ statText(project.stats.parsedDocuments, project.stats.documents) }}</small>
            <small>事实 {{ statText(project.stats.confirmedFacts, project.stats.facts) }}</small>
            <small>章节 {{ statText(project.stats.approvedChapters, project.stats.chapters) }}</small>
            <small>成员 {{ project.stats.members }}</small>
            <small>里程碑 {{ statText(project.stats.completedMilestones, project.stats.milestones) }}</small>
            <small>资料清单 {{ statText(project.stats.completedRequiredMaterials ?? 0, project.stats.requiredMaterials ?? 0) }}</small>
            <small>问题 {{ project.stats.openIssues }}</small>
          </div>
          <small>{{ project.owner }} · {{ project.phase }} · {{ project.confidentiality }}</small>
        </el-card>
      </el-col>
    </el-row>
  </div>

  <el-drawer v-model="drawerOpen" size="62%" :title="profile ? `${profile.name}｜${profile.code}` : '项目详情'">
    <template v-if="profile">
      <div class="metric-grid" style="margin-bottom: 16px">
        <el-card class="metric-card" shadow="never"><span>初始化包</span><strong>{{ profile.initialization.packageReady ? '已生成' : '待补齐' }}</strong></el-card>
        <el-card class="metric-card" shadow="never"><span>成员</span><strong>{{ profile.stats.members }}</strong></el-card>
        <el-card class="metric-card" shadow="never"><span>里程碑</span><strong>{{ statText(profile.stats.completedMilestones, profile.stats.milestones) }}</strong></el-card>
        <el-card class="metric-card" shadow="never"><span>阻断问题</span><strong>{{ profile.stats.blockingIssues }}</strong></el-card>
      </div>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="基本信息" name="profile">
          <el-alert v-if="profile.actions?.readonly" type="warning" show-icon :closable="false" style="margin-bottom: 12px">
            <template #title>{{ profile.actions?.readonlyReason || '当前项目处于只读状态，项目中心基础资料不可直接修改。' }}</template>
          </el-alert>
          <el-form label-position="top" :disabled="!profile.actions?.canEdit">
            <el-row :gutter="14">
              <el-col :span="12"><el-form-item label="项目名称"><el-input v-model="profile.name" /></el-form-item></el-col>
              <el-col :span="12"><el-form-item label="项目编号"><el-input :model-value="profile.code" disabled /></el-form-item></el-col>
              <el-col :span="12"><el-form-item label="项目类型"><el-input v-model="profile.type" /></el-form-item></el-col>
              <el-col :span="12"><el-form-item label="项目地点"><el-input v-model="profile.location" /></el-form-item></el-col>
              <el-col :span="12"><el-form-item label="负责人"><el-input v-model="profile.owner" /></el-form-item></el-col>
              <el-col :span="12"><el-form-item label="当前阶段"><el-input v-model="profile.phase" /></el-form-item></el-col>
              <el-col :span="8"><el-form-item label="进度"><el-slider v-model="profile.progress" /></el-form-item></el-col>
              <el-col :span="8"><el-form-item label="风险"><el-select v-model="profile.risk"><el-option v-for="risk in ['阻断', '严重', '一般', '提示']" :key="risk" :label="risk" :value="risk" /></el-select></el-form-item></el-col>
              <el-col :span="8"><el-form-item label="密级"><el-select v-model="profile.confidentiality"><el-option v-for="level in center?.confidentialityLevels ?? []" :key="level" :label="level" :value="level" /></el-select></el-form-item></el-col>
              <el-col :span="12"><el-form-item label="计划开始"><el-input v-model="profile.plannedStart" placeholder="YYYY-MM-DD" /></el-form-item></el-col>
              <el-col :span="12"><el-form-item label="计划完成"><el-input v-model="profile.plannedEnd" placeholder="YYYY-MM-DD" /></el-form-item></el-col>
              <el-col :span="12"><el-form-item label="模板"><el-select v-model="profile.templateId" clearable><el-option v-for="tpl in templateOptions" :key="tpl.id" :label="`${tpl.name} ${tpl.version}`" :value="tpl.id" /></el-select></el-form-item></el-col>
              <el-col :span="12"><el-form-item label="模板版本"><el-input v-model="profile.templateVersion" /></el-form-item></el-col>
              <el-col :span="12"><el-form-item label="地区"><el-input v-model="profile.region" /></el-form-item></el-col>
              <el-col :span="12"><el-form-item label="地区/初始化规则"><el-select v-model="profile.regionRuleId" filterable clearable><el-option v-for="rule in regionRuleOptions" :key="rule.id" :label="`${rule.name}｜${rule.region}｜${rule.version}`" :value="rule.id" /></el-select></el-form-item></el-col>
              <el-col :span="24"><el-form-item label="项目说明"><el-input v-model="profile.description" type="textarea" :rows="3" /></el-form-item></el-col>
            </el-row>
          </el-form>
          <div class="topbar-actions">
            <el-button type="primary" :disabled="!profile.actions?.canEdit" @click="saveProfile">保存</el-button>
            <el-button :disabled="!profile.actions?.canInitialize" @click="initializePackage">补齐初始化包</el-button>
            <el-button @click="previewGate('已关闭')">关闭门禁</el-button>
            <el-button :disabled="!profile.actions?.canClose" @click="setStatus('已关闭')">关闭项目</el-button>
            <el-button @click="previewGate('已归档')">归档门禁</el-button>
            <el-button :disabled="!profile.actions?.canArchive" @click="setStatus('已归档')">归档项目</el-button>
            <el-button :disabled="!profile.actions?.canReopen" @click="setStatus('进行中')">重新打开</el-button>
            <el-button :disabled="!profile.actions?.canCopy" @click="openCopyDialog">复制项目</el-button>
          </div>
        </el-tab-pane>

        <el-tab-pane label="成员" name="members">
          <div class="toolbar">
            <div class="topbar-actions">
              <el-select v-model="memberForm.userId" filterable placeholder="选择用户" style="width: 220px"><el-option v-for="user in userOptions" :key="user.id" :label="`${user.name}｜${user.department}`" :value="user.id" /></el-select>
              <el-select v-model="memberForm.role" style="width: 160px"><el-option v-for="role in ['项目负责人','项目管理员','编制人员','审核人员','项目成员']" :key="role" :label="role" :value="role" /></el-select>
              <el-button type="primary" :disabled="!profile.actions?.canEdit" @click="addMemberToProfile">添加/更新成员</el-button>
            </div>
          </div>
          <el-table :data="profile.members" border>
            <el-table-column prop="name" label="姓名" />
            <el-table-column prop="department" label="部门" />
            <el-table-column prop="role" label="项目角色" />
            <el-table-column prop="email" label="邮箱" />
            <el-table-column label="操作" width="120"><template #default="scope"><el-button link type="danger" :disabled="!profile.actions?.canEdit" @click="removeMember(scope.row.userId)">移除</el-button></template></el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="里程碑" name="milestones">
          <div class="toolbar">
            <div class="topbar-actions">
              <el-input v-model="milestoneForm.name" placeholder="里程碑名称" style="width: 180px" />
              <el-input v-model="milestoneForm.owner" placeholder="负责人" style="width: 140px" />
              <el-input v-model="milestoneForm.dueAt" placeholder="YYYY-MM-DD" style="width: 140px" />
              <el-button type="primary" :disabled="!profile.actions?.canEdit" @click="addMilestoneToProfile">添加里程碑</el-button>
            </div>
          </div>
          <el-table :data="profile.milestones" border>
            <el-table-column label="名称" min-width="180"><template #default="scope"><el-input v-model="scope.row.name" /></template></el-table-column>
            <el-table-column label="负责人" width="150"><template #default="scope"><el-input v-model="scope.row.owner" /></template></el-table-column>
            <el-table-column label="状态" width="130"><template #default="scope"><el-select v-model="scope.row.status"><el-option v-for="status in ['未开始','进行中','已完成','已逾期']" :key="status" :label="status" :value="status" /></el-select></template></el-table-column>
            <el-table-column label="计划日期" width="150"><template #default="scope"><el-input v-model="scope.row.dueAt" /></template></el-table-column>
            <el-table-column label="操作" width="120"><template #default="scope"><el-button type="primary" link :disabled="!profile.actions?.canEdit" @click="saveMilestone(scope.row)">保存</el-button></template></el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="初始化包与门禁" name="init">
          <div class="toolbar">
            <div>
              <strong>初始化包</strong>
              <p style="margin: 4px 0 0; color: #6b7c88">资料清单、事实框架、章节目录和成果项均由项目中心统一初始化。</p>
            </div>
            <el-button :disabled="!profile.actions?.canInitialize" type="primary" @click="initializePackage">生成/补齐初始化包</el-button>
          </div>
          <el-row :gutter="12" style="margin-bottom: 12px">
            <el-col v-for="check in profile.initialization.checks ?? []" :key="check.key" :span="8">
              <el-card shadow="never" class="metric-card">
                <span>{{ check.label }}</span>
                <strong><el-tag :type="check.passed ? 'success' : 'warning'">{{ check.passed ? '通过' : '待完善' }}</el-tag></strong>
              </el-card>
            </el-col>
          </el-row>

          <el-alert v-if="profile.initialization.missing?.length" type="warning" show-icon :closable="false" style="margin-bottom: 12px">
            <template #title>初始化包仍有 {{ profile.initialization.missing.length }} 项待完善：{{ profile.initialization.missing.map((item) => item.label).join('、') }}</template>
          </el-alert>

          <el-divider content-position="left">资料清单</el-divider>
          <el-table :data="profile.materialRequirements ?? []" border>
            <el-table-column prop="category" label="资料类别" width="120" />
            <el-table-column prop="name" label="资料名称" min-width="260" />
            <el-table-column label="必备" width="80"><template #default="scope"><el-tag :type="scope.row.required ? 'danger' : 'info'">{{ scope.row.required ? '必备' : '可选' }}</el-tag></template></el-table-column>
            <el-table-column label="状态" width="150">
              <template #default="scope">
                <el-select v-model="scope.row.status" size="small">
                  <el-option v-for="status in materialStatuses" :key="status" :label="status" :value="status" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="来源" width="180"><template #default="scope"><el-input v-model="scope.row.sourceId" size="small" placeholder="文档ID/说明" /></template></el-table-column>
            <el-table-column label="操作" width="120"><template #default="scope"><el-button link type="primary" @click="saveMaterial(scope.row)">保存</el-button></template></el-table-column>
          </el-table>

          <el-divider content-position="left">状态门禁</el-divider>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-card shadow="never">
                <div class="panel-title"><h2>关闭门禁</h2><el-tag :type="gateType(profile.statusGates?.close?.allowed)">{{ profile.statusGates?.close?.allowed ? '可关闭' : '阻断' }}</el-tag></div>
                <p>{{ gateSummary(profile.statusGates?.close?.blockers, profile.statusGates?.close?.warnings) }}</p>
                <el-tag v-for="item in profile.statusGates?.close?.blockers ?? []" :key="item.code" type="danger" style="margin: 0 6px 6px 0">{{ item.message }} {{ item.count ?? '' }}</el-tag>
                <el-tag v-for="item in profile.statusGates?.close?.warnings ?? []" :key="item.code" type="warning" style="margin: 0 6px 6px 0">{{ item.message }} {{ item.count ?? '' }}</el-tag>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card shadow="never">
                <div class="panel-title"><h2>归档门禁</h2><el-tag :type="gateType(profile.statusGates?.archive?.allowed)">{{ profile.statusGates?.archive?.allowed ? '可归档' : '阻断' }}</el-tag></div>
                <p>{{ gateSummary(profile.statusGates?.archive?.blockers, profile.statusGates?.archive?.warnings) }}</p>
                <el-tag v-for="item in profile.statusGates?.archive?.blockers ?? []" :key="item.code" type="danger" style="margin: 0 6px 6px 0">{{ item.message }} {{ item.count ?? '' }}</el-tag>
                <el-tag v-for="item in profile.statusGates?.archive?.warnings ?? []" :key="item.code" type="warning" style="margin: 0 6px 6px 0">{{ item.message }} {{ item.count ?? '' }}</el-tag>
              </el-card>
            </el-col>
          </el-row>

          <el-divider content-position="left">初始化记录</el-divider>
          <el-table :data="profile.initializationRecords ?? []" border empty-text="暂无初始化记录">
            <el-table-column prop="packageVersion" label="版本" width="120" />
            <el-table-column prop="status" label="状态" width="120" />
            <el-table-column prop="createdBy" label="创建人" width="140" />
            <el-table-column prop="createdAt" label="创建时间" min-width="200" />
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="迁移与修订" name="migration">
          <div class="toolbar">
            <div>
              <strong>模板/地区规则迁移差异</strong>
              <p style="margin: 4px 0 0; color: #6b7c88">只分析项目中心初始化骨架差异，不自动删除现有资料、事实、章节或成果项。</p>
            </div>
            <div class="topbar-actions">
              <el-button @click="syncMigrationFormFromProfile">使用当前配置</el-button>
              <el-button type="primary" :disabled="!profile.actions?.canCreateMigrationPlan" @click="previewMigration">预览差异</el-button>
              <el-button :disabled="!profile.actions?.canCreateMigrationPlan" @click="createMigrationPlan">生成迁移计划</el-button>
            </div>
          </div>
          <el-row :gutter="14" style="margin-bottom: 14px">
            <el-col :span="8"><el-form-item label="目标模板"><el-select v-model="migrationForm.templateId" clearable><el-option v-for="tpl in templateOptions" :key="tpl.id" :label="`${tpl.name} ${tpl.version}`" :value="tpl.id" /></el-select></el-form-item></el-col>
            <el-col :span="8"><el-form-item label="目标模板版本"><el-input v-model="migrationForm.templateVersion" /></el-form-item></el-col>
            <el-col :span="8"><el-form-item label="目标地区规则"><el-select v-model="migrationForm.regionRuleId" filterable clearable><el-option v-for="rule in regionRuleOptions" :key="rule.id" :label="`${rule.name}｜${rule.region}｜${rule.version}`" :value="rule.id" /></el-select></el-form-item></el-col>
          </el-row>

          <el-alert v-if="profile.migrationPreview" :type="profile.migrationPreview.impactCount ? 'warning' : 'success'" show-icon :closable="false" style="margin-bottom: 12px">
            <template #title>影响项 {{ profile.migrationPreview.impactCount }} 个，风险 {{ profile.migrationPreview.riskLevel }}：{{ profile.migrationPreview.recommendations.join('；') }}</template>
          </el-alert>
          <el-row v-if="profile.migrationPreview" :gutter="12" style="margin-bottom: 12px">
            <el-col v-for="(section, key) in profile.migrationPreview.sections" :key="key" :span="6">
              <el-card shadow="never" class="metric-card">
                <span>{{ section.label }}</span>
                <strong>{{ section.impactCount }}</strong>
                <small>新增 {{ section.added.length }} / 移除 {{ section.removed.length }} / 变化 {{ section.changed.length }}</small>
              </el-card>
            </el-col>
          </el-row>

          <el-divider content-position="left">迁移计划</el-divider>
          <el-table :data="profile.migrationPlans ?? []" border empty-text="暂无迁移计划">
            <el-table-column prop="id" label="计划ID" width="190" />
            <el-table-column prop="status" label="状态" width="100" />
            <el-table-column prop="riskLevel" label="风险" width="90" />
            <el-table-column label="回滚影响" min-width="170"><template #default="scope">
              <el-tag :type="scope.row.rollbackImpact?.riskLevel === '中' ? 'warning' : 'info'">{{ scope.row.rollbackImpact?.summary || '暂无影响' }}</el-tag>
            </template></el-table-column>
            <el-table-column label="审批/回滚" min-width="220"><template #default="scope">
              <span v-if="scope.row.approval?.approvedBy">通过：{{ scope.row.approval.approvedBy }}</span>
              <span v-else-if="scope.row.rejection?.rejectedBy">驳回：{{ scope.row.rejection.rejectedBy }}</span>
              <span v-else-if="scope.row.rollback?.rolledBackBy">回滚：{{ scope.row.rollback.rolledBackBy }}</span>
              <span v-else>待处理</span>
            </template></el-table-column>
            <el-table-column label="目标规则" min-width="220"><template #default="scope">{{ scope.row.toRegionRuleId }} / {{ scope.row.toRuleVersion }}</template></el-table-column>
            <el-table-column prop="createdBy" label="创建人" width="120" />
            <el-table-column label="操作" width="260"><template #default="scope">
              <el-button link type="success" :disabled="!scope.row.actions?.canApprove || !profile.actions?.canApproveMigrationPlan" @click="approveMigrationPlan(scope.row.id)">审批</el-button>
              <el-button link type="warning" :disabled="!scope.row.actions?.canReject || !profile.actions?.canRejectMigrationPlan" @click="rejectMigrationPlan(scope.row.id)">驳回</el-button>
              <el-button link type="primary" :disabled="!scope.row.actions?.canApply || !profile.actions?.canApplyMigrationPlan" @click="applyMigrationPlan(scope.row.id)">应用</el-button>
              <el-button link type="danger" :disabled="!scope.row.actions?.canRollback || !profile.actions?.canRollbackMigrationPlan" @click="rollbackMigrationPlan(scope.row.id)">回滚</el-button>
            </template></el-table-column>
          </el-table>

          <el-divider content-position="left">项目修订链</el-divider>
          <el-row :gutter="14" style="margin-bottom: 12px">
            <el-col :span="8"><el-input v-model="revisionForm.title" placeholder="修订标题" /></el-col>
            <el-col :span="12"><el-input v-model="revisionForm.reason" placeholder="修订原因" /></el-col>
            <el-col :span="4"><el-button type="primary" :disabled="!profile.actions?.canCreateRevision" @click="createRevision">创建修订</el-button></el-col>
          </el-row>
          <el-table :data="profile.revisions ?? []" border empty-text="暂无项目修订">
            <el-table-column prop="revisionNo" label="修订号" width="100" />
            <el-table-column prop="title" label="标题" min-width="180" />
            <el-table-column prop="reason" label="原因" min-width="220" />
            <el-table-column prop="status" label="状态" width="100" />
            <el-table-column prop="createdBy" label="创建人" width="120" />
            <el-table-column label="操作" width="120"><template #default="scope"><el-button link type="primary" :disabled="scope.row.status !== '草稿' || !profile.actions?.canCloseRevision" @click="closeRevision(scope.row.id)">确认关闭</el-button></template></el-table-column>
          </el-table>
        </el-tab-pane>

      </el-tabs>
    </template>
  </el-drawer>

  <el-dialog v-model="form.open" title="新建项目向导" width="760px">
    <el-steps :active="wizardStep" finish-status="success" style="margin-bottom: 20px">
      <el-step title="基本信息" />
      <el-step title="模板与密级" />
      <el-step title="成员与里程碑" />
    </el-steps>
    <el-form label-position="top">
      <template v-if="wizardStep === 0">
        <el-row :gutter="14">
          <el-col :span="12"><el-form-item label="项目名称"><el-input v-model="form.name" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="项目类型"><el-input v-model="form.type" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="项目地点"><el-input v-model="form.location" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="负责人"><el-input v-model="form.owner" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="计划开始"><el-input v-model="form.plannedStart" placeholder="YYYY-MM-DD" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="计划完成"><el-input v-model="form.plannedEnd" placeholder="YYYY-MM-DD" /></el-form-item></el-col>
        </el-row>
      </template>
      <template v-else-if="wizardStep === 1">
        <el-row :gutter="14">
          <el-col :span="12"><el-form-item label="报告模板"><el-select v-model="form.templateId" clearable @change="bindSelectedTemplate"><el-option v-for="tpl in templateOptions" :key="tpl.id" :label="`${tpl.name} ${tpl.version}`" :value="tpl.id" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="模板版本"><el-input v-model="form.templateVersion" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="项目密级"><el-select v-model="form.confidentiality"><el-option v-for="level in center?.confidentialityLevels ?? []" :key="level" :label="level" :value="level" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="地区"><el-input v-model="form.region" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="地区/初始化规则"><el-select v-model="form.regionRuleId" filterable @change="bindSelectedRegionRule"><el-option v-for="rule in regionRuleOptions" :key="rule.id" :label="`${rule.name}｜${rule.region}｜${rule.version}`" :value="rule.id" /></el-select></el-form-item></el-col>
          <el-col :span="24"><el-form-item label="项目说明"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item></el-col>
        </el-row>
      </template>
      <template v-else>
        <div class="toolbar">
          <div class="topbar-actions">
            <el-select v-model="memberForm.userId" filterable placeholder="选择成员" style="width: 220px"><el-option v-for="user in userOptions" :key="user.id" :label="`${user.name}｜${user.department}`" :value="user.id" /></el-select>
            <el-select v-model="memberForm.role" style="width: 150px"><el-option v-for="role in ['项目负责人','项目管理员','编制人员','审核人员','项目成员']" :key="role" :label="role" :value="role" /></el-select>
            <el-button @click="addWizardMember">添加成员</el-button>
          </div>
        </div>
        <el-table :data="form.members" border style="margin-bottom: 14px"><el-table-column prop="userId" label="用户ID" /><el-table-column prop="role" label="项目角色" /></el-table>
        <el-table :data="form.milestones" border><el-table-column prop="name" label="默认里程碑" /><el-table-column prop="owner" label="负责人" /><el-table-column prop="status" label="状态" /></el-table>
      </template>
    </el-form>
    <template #footer>
      <el-button @click="form.open = false">取消</el-button>
      <el-button @click="saveWizardDraft">保存草稿</el-button>
      <el-button :disabled="wizardStep === 0" @click="wizardStep--">上一步</el-button>
      <el-button v-if="wizardStep < 2" type="primary" @click="wizardStep++">下一步</el-button>
      <el-button v-else type="primary" @click="submitWizard">创建项目</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="copyForm.open" title="复制项目" width="420px">
    <el-form label-position="top">
      <el-form-item label="新项目名称"><el-input v-model="copyForm.name" /></el-form-item>
      <el-checkbox v-model="copyForm.copySettings">复制模板与密级</el-checkbox>
      <el-checkbox v-model="copyForm.copyMembers">复制成员</el-checkbox>
      <el-checkbox v-model="copyForm.copyMilestones">复制里程碑</el-checkbox>
    </el-form>
    <template #footer>
      <el-button @click="copyForm.open = false">取消</el-button>
      <el-button type="primary" @click="submitCopy">复制</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.project-stage-card {
  margin-bottom: 10px;
  border: 1px solid #e1e8ef;
  border-radius: 4px;
}

.project-stage-card :deep(.el-card__body) {
  padding: 14px 18px 12px;
}

.project-stage-flow {
  position: relative;
  display: grid;
  grid-template-columns: repeat(7, minmax(86px, 1fr));
  align-items: start;
  gap: 4px;
}

.project-stage-flow::before {
  content: "";
  position: absolute;
  top: 13px;
  left: 3.5%;
  right: 3.5%;
  height: 2px;
  background: #d8e0e8;
}

.project-stage-item {
  position: relative;
  z-index: 1;
  display: grid;
  justify-items: center;
  min-width: 0;
  color: #4d6276;
  text-align: center;
}

.stage-index {
  display: grid;
  width: 28px;
  height: 28px;
  margin-bottom: 8px;
  place-items: center;
  border: 2px solid #cdd7e2;
  border-radius: 50%;
  background: #ffffff;
  color: #8293a4;
  font-weight: 700;
  line-height: 1;
}

.project-stage-item.active .stage-index,
.project-stage-item.passed .stage-index {
  border-color: #20a681;
  background: #20a681;
  color: #ffffff;
  box-shadow: 0 3px 10px rgba(32, 166, 129, 0.22);
}

.stage-title {
  color: #223548;
  font-size: 14px;
  font-weight: 700;
  line-height: 1.3;
}

.project-stage-item.active .stage-title {
  color: #118363;
}

.stage-subtitle {
  margin-top: 5px;
  color: #7d8b98;
  font-size: 12px;
  line-height: 1.2;
  white-space: nowrap;
}

.overview-panel {
  margin-bottom: 12px;
  border: 1px solid #dfe8f0;
  border-radius: 4px;
}

.overview-panel :deep(.el-card__body) {
  padding: 12px 14px;
}

.overview-title {
  margin-bottom: 10px;
  color: #1f2d3d;
  font-size: 15px;
  font-weight: 700;
}

.overview-title span {
  color: #8592a1;
  font-size: 12px;
  font-weight: 500;
}

.overview-metric-row {
  display: grid;
  grid-template-columns: repeat(6, minmax(118px, 1fr));
  gap: 12px;
}

.overview-metric-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 56px;
  padding: 10px 12px;
  border: 1px solid #e7edf3;
  border-radius: 4px;
  background: #ffffff;
}

.overview-metric-text {
  display: grid;
  gap: 6px;
}

.overview-metric-text span {
  color: #7a8794;
  font-size: 12px;
}

.overview-metric-text strong {
  color: #1c2f43;
  font-size: 24px;
  line-height: 1;
}

.overview-icon {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 50%;
  font-size: 16px;
  font-weight: 800;
}

@media (max-width: 1180px) {
  .overview-metric-row {
    grid-template-columns: repeat(3, minmax(150px, 1fr));
  }

  .project-stage-flow {
    overflow-x: auto;
    grid-template-columns: repeat(7, 120px);
    padding-bottom: 4px;
  }
}
</style>
