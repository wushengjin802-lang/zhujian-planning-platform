<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { usePlatformStore } from "../stores/platform";
import {
  addProjectMember,
  addProjectMilestone,
  changeProjectStatus,
  initializeProjectPackage,
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
    <div class="metric-grid" style="margin-bottom: 16px">
      <el-card v-for="metric in center?.metrics ?? []" :key="metric.key" class="metric-card" shadow="never">
        <div>
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
        </div>
        <el-tag :type="metric.tone === 'danger' ? 'danger' : metric.tone === 'success' ? 'success' : metric.tone === 'primary' ? 'primary' : 'info'">{{ metric.key }}</el-tag>
      </el-card>
    </div>

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
          <el-form label-position="top">
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
              <el-button type="primary" @click="addMemberToProfile">添加/更新成员</el-button>
            </div>
          </div>
          <el-table :data="profile.members" border>
            <el-table-column prop="name" label="姓名" />
            <el-table-column prop="department" label="部门" />
            <el-table-column prop="role" label="项目角色" />
            <el-table-column prop="email" label="邮箱" />
            <el-table-column label="操作" width="120"><template #default="scope"><el-button link type="danger" @click="removeMember(scope.row.userId)">移除</el-button></template></el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="里程碑" name="milestones">
          <div class="toolbar">
            <div class="topbar-actions">
              <el-input v-model="milestoneForm.name" placeholder="里程碑名称" style="width: 180px" />
              <el-input v-model="milestoneForm.owner" placeholder="负责人" style="width: 140px" />
              <el-input v-model="milestoneForm.dueAt" placeholder="YYYY-MM-DD" style="width: 140px" />
              <el-button type="primary" @click="addMilestoneToProfile">添加里程碑</el-button>
            </div>
          </div>
          <el-table :data="profile.milestones" border>
            <el-table-column label="名称" min-width="180"><template #default="scope"><el-input v-model="scope.row.name" /></template></el-table-column>
            <el-table-column label="负责人" width="150"><template #default="scope"><el-input v-model="scope.row.owner" /></template></el-table-column>
            <el-table-column label="状态" width="130"><template #default="scope"><el-select v-model="scope.row.status"><el-option v-for="status in ['未开始','进行中','已完成','已逾期']" :key="status" :label="status" :value="status" /></el-select></template></el-table-column>
            <el-table-column label="计划日期" width="150"><template #default="scope"><el-input v-model="scope.row.dueAt" /></template></el-table-column>
            <el-table-column label="操作" width="120"><template #default="scope"><el-button type="primary" link @click="saveMilestone(scope.row)">保存</el-button></template></el-table-column>
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
