import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";
import type { AppUser, BootstrapPayload, DashboardPayload, FactItem, InvestmentEstimate, PlatformStatus, ProjectDocument, QualityIssue, ReportChapter } from "../types";
import {
  calculateInvestmentEstimate,
  confirmInvestmentEstimate,
  createDocument,
  createProject,
  createQualityCheckJob,
  generateChapterDraft,
  getCurrentUser,
  loadBootstrap,
  loadDashboard,
  loadInvestmentEstimate,
  loadPlatformStatus,
  login,
  logout,
  requestArtifactExport,
  runDocumentParse,
  updateChapter,
  updateFact,
  updateQualityIssue,
  uploadDocument
} from "../api/client";

const emptyPayload: BootstrapPayload = {
  navGroups: [],
  workflow: [],
  routeMeta: {},
  projects: [],
  documents: [],
  facts: [],
  chapters: [],
  qualityIssues: [],
  artifacts: [],
  users: [],
  templates: [],
  knowledgeItems: [],
  auditLogs: [],
  qualityRules: [],
  citations: [],
  documentChunks: []
};

export const usePlatformStore = defineStore("platform", () => {
  const data = ref<BootstrapPayload>(emptyPayload);
  const loading = ref(false);
  const currentProjectId = ref("P001");
  const currentUser = ref<AppUser | null>(null);
  const platformStatus = ref<PlatformStatus | null>(null);
  const investmentEstimate = ref<InvestmentEstimate | null>(null);
  const dashboard = ref<DashboardPayload | null>(null);
  const dashboardScope = ref<"current" | "all">("current");
  const dashboardLoading = ref(false);
  const notice = ref("正在加载项目数据");

  const currentProject = computed(() => data.value.projects.find((item) => item.id === currentProjectId.value) ?? data.value.projects[0]);
  const projectDocuments = computed(() => data.value.documents.filter((item) => item.projectId === currentProject.value?.id));
  const projectFacts = computed(() => data.value.facts.filter((item) => item.projectId === currentProject.value?.id));
  const projectChapters = computed(() => data.value.chapters.filter((item) => item.projectId === currentProject.value?.id));
  const projectIssues = computed(() => data.value.qualityIssues.filter((item) => item.projectId === currentProject.value?.id));
  const projectArtifacts = computed(() => data.value.artifacts.filter((item) => item.projectId === currentProject.value?.id));
  const blocked = computed(() => projectIssues.value.some((item) => item.severity === "阻断" && item.status !== "已关闭"));

  async function refresh() {
    loading.value = true;
    try {
      data.value = await loadBootstrap();
      platformStatus.value = await loadPlatformStatus();
      if (!data.value.projects.some((item) => item.id === currentProjectId.value) && data.value.projects[0]) {
        currentProjectId.value = data.value.projects[0].id;
      }
      notice.value = "项目数据已更新";
    } catch (error) {
      notice.value = error instanceof Error ? error.message : "数据加载失败";
    } finally {
      loading.value = false;
    }
  }

  async function fetchDashboard(scope: "current" | "all" = dashboardScope.value) {
    if (!currentUser.value) return;
    dashboardScope.value = scope;
    dashboardLoading.value = true;
    try {
      dashboard.value = await loadDashboard(scope === "current" ? currentProject.value?.id : undefined);
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : "工作台数据加载失败");
    } finally {
      dashboardLoading.value = false;
    }
  }

  async function bootstrap() {
    await refresh();
    try {
      currentUser.value = await getCurrentUser();
      await fetchDashboard();
    } catch {
      currentUser.value = null;
      dashboard.value = null;
    }
  }

  async function runAction(label: string, operation: () => Promise<unknown>) {
    if (!currentUser.value) {
      ElMessage.warning("请先登录后再执行写入操作");
      return;
    }
    loading.value = true;
    try {
      await operation();
      await refresh();
      await fetchDashboard();
      ElMessage.success(`${label}完成`);
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : `${label}失败`);
    } finally {
      loading.value = false;
    }
  }

  async function doLogin(email: string, password: string) {
    loading.value = true;
    try {
      currentUser.value = await login(email, password);
      await refresh();
      await fetchDashboard();
      ElMessage.success(`已登录：${currentUser.value.name}`);
    } finally {
      loading.value = false;
    }
  }

  async function doLogout() {
    await logout();
    currentUser.value = null;
    dashboard.value = null;
    ElMessage.success("已退出登录");
  }

  function addProject(input: { name: string; location?: string }) {
    return runAction("项目建档", () => createProject({ ...input, owner: "项目负责人" }));
  }

  function addDocument(input: { name: string; category?: string }) {
    if (!currentProject.value) return Promise.resolve();
    return runAction("资料登记", () => createDocument(currentProject.value.id, { ...input, source: "人工登记" }));
  }

  function upload(file: File) {
    if (!currentProject.value) return Promise.resolve();
    return runAction("资料上传", () => uploadDocument(currentProject.value.id, file));
  }

  function parse(doc: ProjectDocument) {
    return runAction("资料解析", () => runDocumentParse(doc.id));
  }

  function confirmFact(fact: FactItem) {
    return runAction("事实确认", () => updateFact(fact.id, { status: "已确认" }));
  }

  function lockFact(fact: FactItem) {
    return runAction("事实锁定", () => updateFact(fact.id, { status: "已锁定" }));
  }

  function resolveFact(fact: FactItem, value: string) {
    return runAction("事实冲突处理", () => updateFact(fact.id, { value, status: "已确认" }));
  }

  function generateChapter(chapter: ReportChapter) {
    return runAction("章节初稿生成", () => generateChapterDraft(chapter.id));
  }

  function submitChapter(chapter: ReportChapter) {
    return runAction("章节提交审核", () => updateChapter(chapter.id, { status: "待审核" }));
  }

  function approveChapter(chapter: ReportChapter) {
    return runAction("章节审核", () => updateChapter(chapter.id, { status: "已审核" }));
  }

  function closeIssue(issue: QualityIssue) {
    return runAction("质量问题关闭", () => updateQualityIssue(issue.id, "已关闭"));
  }

  function runQualityCheck() {
    if (!currentProject.value) return Promise.resolve();
    return runAction("质量检查", () => createQualityCheckJob(currentProject.value.id));
  }

  function exportArtifact(id: string) {
    return runAction("成果导出", () => requestArtifactExport(id));
  }

  async function fetchInvestmentEstimate() {
    if (!currentProject.value) return;
    loading.value = true;
    try {
      investmentEstimate.value = await loadInvestmentEstimate(currentProject.value.id);
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : "投资测算加载失败");
    } finally {
      loading.value = false;
    }
  }

  function runInvestmentCalculation() {
    if (!currentProject.value) return Promise.resolve();
    return runAction("投资测算", async () => {
      investmentEstimate.value = await calculateInvestmentEstimate(currentProject.value.id);
    });
  }

  function confirmInvestment() {
    if (!investmentEstimate.value) return Promise.resolve();
    return runAction("测算确认", async () => {
      investmentEstimate.value = await confirmInvestmentEstimate(investmentEstimate.value!.id);
    });
  }

  return {
    data,
    loading,
    notice,
    currentUser,
    platformStatus,
    investmentEstimate,
    dashboard,
    dashboardScope,
    dashboardLoading,
    currentProjectId,
    currentProject,
    projectDocuments,
    projectFacts,
    projectChapters,
    projectIssues,
    projectArtifacts,
    blocked,
    bootstrap,
    refresh,
    fetchDashboard,
    doLogin,
    doLogout,
    addProject,
    addDocument,
    upload,
    parse,
    confirmFact,
    lockFact,
    resolveFact,
    generateChapter,
    submitChapter,
    approveChapter,
    closeIssue,
    runQualityCheck,
    exportArtifact,
    fetchInvestmentEstimate,
    runInvestmentCalculation,
    confirmInvestment
  };
});
