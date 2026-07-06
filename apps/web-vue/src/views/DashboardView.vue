<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  BellFilled,
  CircleCheck,
  Clock,
  DataBoard,
  DocumentChecked,
  Files,
  Finished,
  Loading,
  Memo,
  Opportunity,
  Refresh,
  Right,
  Tickets,
  TrendCharts,
  Warning
} from "@element-plus/icons-vue";
import type { DashboardMetric, DashboardTone } from "../types";
import { usePlatformStore } from "../stores/platform";

const store = usePlatformStore();
const router = useRouter();
const activeWorkTab = ref<"todo" | "review">("todo");
const taskFilter = ref("全部");

const dashboard = computed(() => store.dashboard);
const visibleTasks = computed(() => {
  const tasks = dashboard.value?.tasks ?? [];
  return taskFilter.value === "全部" ? tasks : tasks.filter((item) => item.status === taskFilter.value);
});
const latestProject = computed(() => dashboard.value?.projects[0]);

const metricIcons: Record<string, unknown> = {
  projectProgress: TrendCharts,
  pendingWork: Tickets,
  pendingReview: DocumentChecked,
  blockingIssues: Warning,
  runningTasks: Loading,
  artifacts: Finished
};

const toneType: Record<DashboardTone, "primary" | "success" | "warning" | "danger" | "info"> = {
  primary: "primary",
  success: "success",
  warning: "warning",
  danger: "danger",
  info: "info"
};

function metricIcon(metric: DashboardMetric) {
  return metricIcons[metric.key] ?? DataBoard;
}

function priorityType(priority: string) {
  if (priority === "P0") return "danger";
  if (priority === "P1") return "warning";
  if (priority === "P2") return "primary";
  return "info";
}

function statusType(status: string) {
  if (["失败", "受阻", "有冲突", "需复核"].includes(status)) return "danger";
  if (["运行中", "处理中", "编制中", "待确认", "待审核"].includes(status)) return "warning";
  if (["已完成", "已审核", "已解析", "已确认", "已锁定"].includes(status)) return "success";
  return "info";
}

function progressStatus(percentage: number) {
  if (percentage >= 100) return "success";
  if (percentage < 30) return "warning";
  return undefined;
}

function formatTime(value?: string | null) {
  if (!value) return "暂无时间";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

async function changeScope(value: string | number | boolean | undefined) {
  await store.fetchDashboard(value === "all" ? "all" : "current");
}

function openRoute(route: string, projectId?: string | null) {
  if (projectId && store.data.projects.some((item) => item.id === projectId)) {
    store.currentProjectId = projectId;
  }
  router.push(route);
}

onMounted(() => {
  if (store.currentUser && !store.dashboard) store.fetchDashboard();
});

watch(
  () => store.currentProjectId,
  () => {
    if (store.dashboardScope === "current" && store.currentUser) store.fetchDashboard("current");
  }
);
</script>

<template>
  <section class="dashboard-page" v-loading="store.dashboardLoading">
    <el-card class="dashboard-hero" shadow="never">
      <div>
        <span class="dashboard-kicker">
          {{ dashboard?.roleMode === "management" ? "管理视角" : "个人工作视角" }} · {{ store.currentUser?.role }}
        </span>
        <h2>{{ store.currentUser?.name }}，欢迎回来</h2>
        <p>
          {{ dashboard?.scope === "all" ? "正在查看全部项目的任务、风险与审核状态。" : `正在推进《${store.currentProject?.name ?? "当前项目"}》的第一阶段工作。` }}
        </p>
      </div>
      <div class="hero-actions">
        <el-segmented
          :model-value="store.dashboardScope"
          :options="[
            { label: '当前项目', value: 'current' },
            { label: '全部项目', value: 'all' }
          ]"
          @change="changeScope"
        />
        <el-button :icon="Refresh" :loading="store.dashboardLoading" @click="store.fetchDashboard()">刷新</el-button>
      </div>
    </el-card>

    <section v-if="dashboard" class="dashboard-content">
      <section class="dashboard-metrics">
        <el-card
          v-for="metric in dashboard.metrics"
          :key="metric.key"
          class="dashboard-metric-card"
          shadow="never"
          @click="openRoute(metric.route)"
        >
          <div class="metric-icon" :class="`metric-${metric.tone}`">
            <el-icon><component :is="metricIcon(metric)" /></el-icon>
          </div>
          <div class="metric-copy">
            <span>{{ metric.label }}</span>
            <strong>{{ metric.value }}<small>{{ metric.unit }}</small></strong>
            <p>{{ metric.description }}</p>
          </div>
          <el-tag :type="toneType[metric.tone]" effect="light" round>{{ metric.tone === "danger" ? "需关注" : "实时" }}</el-tag>
        </el-card>
      </section>

      <section class="dashboard-main-grid">
        <el-card class="dashboard-panel workflow-panel" shadow="never">
          <template #header>
            <div class="dashboard-panel-title">
              <div>
                <h3>项目流程进展</h3>
                <p>从资料解析到成果生成的关键节点</p>
              </div>
              <el-tag v-if="latestProject" :type="latestProject.risk === '阻断' || latestProject.risk === '严重' ? 'danger' : 'info'">
                风险：{{ latestProject.risk }}
              </el-tag>
            </div>
          </template>

          <div v-if="latestProject" class="project-overview">
            <div>
              <strong>{{ latestProject.name }}</strong>
              <span>{{ latestProject.type }} · {{ latestProject.location }} · {{ latestProject.owner }}</span>
            </div>
            <div class="project-overview-progress">
              <strong>{{ latestProject.progress }}%</strong>
              <span>{{ latestProject.phase }}</span>
            </div>
          </div>

          <button
            v-for="item in dashboard.workflow"
            :key="item.key"
            type="button"
            class="workflow-progress-row"
            @click="openRoute(item.route)"
          >
            <div class="workflow-name">
              <span>{{ item.name }}</span>
              <small>{{ item.done }}/{{ item.total }}</small>
            </div>
            <el-progress :percentage="item.percentage" :status="progressStatus(item.percentage)" :stroke-width="9" />
            <el-icon><Right /></el-icon>
          </button>
        </el-card>

        <el-card class="dashboard-panel alert-panel" shadow="never">
          <template #header>
            <div class="dashboard-panel-title">
              <div>
                <h3>风险与提醒</h3>
                <p>需要优先关注的流程事件</p>
              </div>
              <el-icon class="header-icon"><BellFilled /></el-icon>
            </div>
          </template>

          <button
            v-for="notice in dashboard.notifications"
            :key="notice.id"
            type="button"
            class="notice-item"
            :class="`notice-${notice.level}`"
            @click="openRoute(notice.route)"
          >
            <el-icon>
              <CircleCheck v-if="notice.level === 'success'" />
              <Warning v-else-if="notice.level === 'danger' || notice.level === 'warning'" />
              <Opportunity v-else />
            </el-icon>
            <span>
              <strong>{{ notice.title }}</strong>
              <small>{{ notice.message }}</small>
            </span>
            <el-icon><Right /></el-icon>
          </button>
        </el-card>
      </section>

      <section class="dashboard-main-grid dashboard-work-grid">
        <el-card class="dashboard-panel work-panel" shadow="never">
          <template #header>
            <div class="dashboard-panel-title work-title">
              <el-tabs v-model="activeWorkTab">
                <el-tab-pane :label="`待办事项 ${dashboard.workItems.length}`" name="todo" />
                <el-tab-pane :label="`待审核 ${dashboard.reviewQueue.length}`" name="review" />
              </el-tabs>
              <span>按优先级排序</span>
            </div>
          </template>

          <div v-if="activeWorkTab === 'todo'" class="work-list">
            <button
              v-for="item in dashboard.workItems.slice(0, 10)"
              :key="item.id"
              type="button"
              class="work-row"
              @click="openRoute(item.route, item.projectId)"
            >
              <el-tag :type="priorityType(item.priority)" effect="dark" size="small">{{ item.priority }}</el-tag>
              <span class="work-main">
                <strong>{{ item.title }}</strong>
                <small>{{ item.projectName }} · {{ item.category }} · {{ item.detail }}</small>
              </span>
              <span class="work-owner">{{ item.owner }}</span>
              <el-tag :type="statusType(item.status)" effect="plain" size="small">{{ item.status }}</el-tag>
              <el-icon><Right /></el-icon>
            </button>
            <el-empty v-if="!dashboard.workItems.length" description="当前没有待办事项" :image-size="70" />
          </div>

          <div v-else class="work-list">
            <button
              v-for="item in dashboard.reviewQueue"
              :key="item.id"
              type="button"
              class="work-row"
              @click="openRoute(item.route, item.projectId)"
            >
              <el-tag :type="priorityType(item.priority)" effect="dark" size="small">{{ item.priority }}</el-tag>
              <span class="work-main">
                <strong>{{ item.title }}</strong>
                <small>{{ item.projectName }} · {{ item.type }} · {{ item.description }}</small>
              </span>
              <span class="work-owner">{{ item.submitter }}</span>
              <el-tag type="warning" effect="plain" size="small">{{ item.status }}</el-tag>
              <el-icon><Right /></el-icon>
            </button>
            <el-empty v-if="!dashboard.reviewQueue.length" description="当前没有待审核事项" :image-size="70" />
          </div>
        </el-card>

        <el-card class="dashboard-panel quick-panel" shadow="never">
          <template #header>
            <div class="dashboard-panel-title">
              <div>
                <h3>快捷操作</h3>
                <p>快速进入高频作业入口</p>
              </div>
              <el-icon class="header-icon"><DataBoard /></el-icon>
            </div>
          </template>
          <button
            v-for="(action, index) in dashboard.quickActions"
            :key="action.key"
            type="button"
            class="quick-action"
            @click="openRoute(action.route)"
          >
            <span class="quick-number">0{{ index + 1 }}</span>
            <span>
              <strong>{{ action.label }}</strong>
              <small>{{ action.description }}</small>
            </span>
            <el-icon><Right /></el-icon>
          </button>
        </el-card>
      </section>

      <section class="dashboard-main-grid dashboard-bottom-grid">
        <el-card class="dashboard-panel task-panel" shadow="never">
          <template #header>
            <div class="dashboard-panel-title">
              <div>
                <h3>异步任务中心</h3>
                <p>资料解析、质量检查和成果导出状态</p>
              </div>
              <el-radio-group v-model="taskFilter" size="small">
                <el-radio-button label="全部" />
                <el-radio-button label="运行中" />
                <el-radio-button label="失败" />
                <el-radio-button label="已完成" />
              </el-radio-group>
            </div>
          </template>

          <el-table :data="visibleTasks" size="small" empty-text="暂无后台任务" max-height="320">
            <el-table-column label="任务" min-width="210">
              <template #default="{ row }">
                <div class="task-name">
                  <strong>{{ row.name }}</strong>
                  <span>{{ row.type }} · {{ row.projectName }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="进度" width="150">
              <template #default="{ row }">
                <el-progress :percentage="row.progress" :show-text="false" :status="row.status === '失败' ? 'exception' : row.status === '已完成' ? 'success' : undefined" />
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="更新时间" width="120">
              <template #default="{ row }">{{ formatTime(row.updatedAt) }}</template>
            </el-table-column>
            <el-table-column width="72" align="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openRoute(row.route, row.projectId)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card class="dashboard-panel activity-panel" shadow="never">
          <template #header>
            <div class="dashboard-panel-title">
              <div>
                <h3>近期活动</h3>
                <p>项目关键操作与审计记录</p>
              </div>
              <el-icon class="header-icon"><Memo /></el-icon>
            </div>
          </template>
          <el-timeline>
            <el-timeline-item
              v-for="activity in dashboard.recentActivities.slice(0, 7)"
              :key="activity.id"
              :timestamp="formatTime(activity.createdAt)"
              placement="top"
            >
              <strong>{{ activity.action }}</strong>
              <p>{{ activity.actor }} · {{ activity.entityType }} {{ activity.entityId ?? "" }}</p>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-if="!dashboard.recentActivities.length" description="暂无活动记录" :image-size="70" />
        </el-card>
      </section>

      <el-card v-if="dashboard.projects.length > 1" class="dashboard-panel project-table-panel" shadow="never">
        <template #header>
          <div class="dashboard-panel-title">
            <div>
              <h3>项目组合概览</h3>
              <p>跨项目比较进度、资料、事实、章节和风险</p>
            </div>
          </div>
        </template>
        <el-table :data="dashboard.projects" size="small">
          <el-table-column prop="name" label="项目" min-width="220" />
          <el-table-column prop="phase" label="当前阶段" width="120" />
          <el-table-column prop="owner" label="负责人" width="120" />
          <el-table-column label="进度" width="160">
            <template #default="{ row }"><el-progress :percentage="row.progress" :stroke-width="8" /></template>
          </el-table-column>
          <el-table-column prop="documents" label="资料解析" width="90" />
          <el-table-column prop="facts" label="事实确认" width="90" />
          <el-table-column prop="chapters" label="章节审核" width="90" />
          <el-table-column label="风险" width="90">
            <template #default="{ row }"><el-tag :type="row.risk === '阻断' || row.risk === '严重' ? 'danger' : 'info'">{{ row.risk }}</el-tag></template>
          </el-table-column>
          <el-table-column label="问题" width="72" align="center">
            <template #default="{ row }"><strong>{{ row.openIssues }}</strong></template>
          </el-table-column>
          <el-table-column width="72" align="right">
            <template #default="{ row }"><el-button link type="primary" @click="openRoute('/projects', row.id)">进入</el-button></template>
          </el-table-column>
        </el-table>
      </el-card>
    </section>

    <el-skeleton v-else :rows="10" animated />
  </section>
</template>

<style scoped>
.dashboard-page {
  display: grid;
  gap: 16px;
}

.dashboard-hero {
  color: #fff;
  border: 0;
  background:
    radial-gradient(circle at 88% 15%, rgba(61, 220, 174, 0.2), transparent 27%),
    linear-gradient(115deg, #173f5b, #176b62 72%, #1c806c);
}

.dashboard-hero :deep(.el-card__body) {
  display: flex;
  min-height: 112px;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 24px 28px;
}

.dashboard-kicker {
  color: #a9f0d8;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1px;
}

.dashboard-hero h2 {
  margin: 8px 0 6px;
  font-size: 25px;
}

.dashboard-hero p {
  margin: 0;
  color: rgba(239, 255, 251, 0.8);
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hero-actions :deep(.el-segmented) {
  --el-segmented-bg-color: rgba(255, 255, 255, 0.14);
  --el-segmented-item-selected-bg-color: #fff;
  --el-segmented-item-selected-color: #176b62;
  color: #fff;
}

.dashboard-content {
  display: grid;
  gap: 16px;
}

.dashboard-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.dashboard-metric-card {
  cursor: pointer;
  border: 1px solid #dbe6eb;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.dashboard-metric-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 28px rgba(38, 75, 95, 0.1);
}

.dashboard-metric-card :deep(.el-card__body) {
  display: grid;
  grid-template-columns: 46px 1fr auto;
  gap: 12px;
  align-items: start;
  padding: 18px;
}

.metric-icon {
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  border-radius: 12px;
  font-size: 21px;
}

.metric-primary { color: #176b62; background: #dff4ed; }
.metric-success { color: #1f7a4d; background: #e3f5e9; }
.metric-warning { color: #9a6200; background: #fff1d0; }
.metric-danger { color: #b52a2a; background: #fde6e6; }
.metric-info { color: #27658a; background: #e3f0f8; }

.metric-copy > span {
  color: #637480;
  font-size: 13px;
}

.metric-copy strong {
  display: block;
  margin: 5px 0 3px;
  color: #17364a;
  font-size: 28px;
}

.metric-copy strong small {
  margin-left: 3px;
  color: #6d7d87;
  font-size: 13px;
  font-weight: 500;
}

.metric-copy p {
  margin: 0;
  color: #87959e;
  font-size: 12px;
}

.dashboard-main-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(310px, 0.75fr);
  gap: 16px;
}

.dashboard-work-grid {
  grid-template-columns: minmax(0, 1.65fr) minmax(280px, 0.65fr);
}

.dashboard-bottom-grid {
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.75fr);
}

.dashboard-panel {
  border: 1px solid #dbe6eb;
  border-radius: 10px;
}

.dashboard-panel-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.dashboard-panel-title h3 {
  margin: 0 0 4px;
  color: #203746;
  font-size: 16px;
}

.dashboard-panel-title p {
  margin: 0;
  color: #82909a;
  font-size: 12px;
}

.header-icon {
  color: #26826d;
  font-size: 22px;
}

.project-overview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
  padding: 14px 16px;
  border-radius: 8px;
  background: #f3f8f7;
}

.project-overview strong,
.project-overview span {
  display: block;
}

.project-overview span {
  margin-top: 5px;
  color: #74858f;
  font-size: 12px;
}

.project-overview-progress {
  text-align: right;
}

.project-overview-progress strong {
  color: #1c806c;
  font-size: 25px;
}

.workflow-progress-row {
  display: grid;
  width: 100%;
  grid-template-columns: 118px 1fr 20px;
  gap: 14px;
  align-items: center;
  padding: 10px 4px;
  border: 0;
  border-bottom: 1px solid #edf2f4;
  text-align: left;
  background: transparent;
  cursor: pointer;
}

.workflow-progress-row:last-child {
  border-bottom: 0;
}

.workflow-progress-row:hover {
  background: #f7faf9;
}

.workflow-name {
  display: flex;
  justify-content: space-between;
  color: #344b59;
  font-size: 13px;
}

.workflow-name small {
  color: #8997a0;
}

.notice-item {
  display: grid;
  width: 100%;
  grid-template-columns: 30px 1fr 20px;
  gap: 10px;
  align-items: center;
  margin-bottom: 9px;
  padding: 12px;
  border: 1px solid transparent;
  border-radius: 8px;
  text-align: left;
  cursor: pointer;
}

.notice-item span strong,
.notice-item span small {
  display: block;
}

.notice-item span strong {
  margin-bottom: 4px;
  font-size: 13px;
}

.notice-item span small {
  color: #778891;
  line-height: 1.45;
}

.notice-danger { color: #a92727; border-color: #f2d2d2; background: #fff5f5; }
.notice-warning { color: #976000; border-color: #f1e0b9; background: #fffbef; }
.notice-info { color: #29688b; border-color: #d4e7f2; background: #f4f9fc; }
.notice-success { color: #27724c; border-color: #d4eadc; background: #f4fbf6; }

.work-title :deep(.el-tabs__header) {
  margin: 0;
}

.work-title > span {
  color: #87959e;
  font-size: 12px;
}

.work-list {
  display: grid;
}

.work-row {
  display: grid;
  width: 100%;
  grid-template-columns: 38px minmax(0, 1fr) 95px 82px 18px;
  gap: 10px;
  align-items: center;
  padding: 12px 4px;
  border: 0;
  border-bottom: 1px solid #edf2f4;
  text-align: left;
  background: transparent;
  cursor: pointer;
}

.work-row:hover {
  background: #f7faf9;
}

.work-main strong,
.work-main small {
  display: block;
}

.work-main strong {
  overflow: hidden;
  color: #304956;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.work-main small {
  margin-top: 4px;
  overflow: hidden;
  color: #81909a;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.work-owner {
  overflow: hidden;
  color: #647783;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quick-action {
  display: grid;
  width: 100%;
  grid-template-columns: 38px 1fr 20px;
  gap: 10px;
  align-items: center;
  padding: 14px 4px;
  border: 0;
  border-bottom: 1px solid #edf2f4;
  text-align: left;
  background: transparent;
  cursor: pointer;
}

.quick-action:hover {
  color: #176b62;
  background: #f7faf9;
}

.quick-number {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border-radius: 9px;
  color: #176b62;
  background: #e2f4ef;
  font-size: 12px;
  font-weight: 700;
}

.quick-action strong,
.quick-action small {
  display: block;
}

.quick-action strong {
  color: #304956;
  font-size: 13px;
}

.quick-action small {
  margin-top: 4px;
  color: #81909a;
  font-size: 12px;
}

.task-name strong,
.task-name span {
  display: block;
}

.task-name strong {
  color: #344b59;
  font-size: 13px;
}

.task-name span {
  margin-top: 3px;
  color: #81909a;
  font-size: 11px;
}

.activity-panel :deep(.el-card__body) {
  max-height: 360px;
  overflow: auto;
}

.activity-panel :deep(.el-timeline-item__content) strong {
  color: #344b59;
  font-size: 13px;
}

.activity-panel :deep(.el-timeline-item__content) p {
  margin: 4px 0 0;
  color: #81909a;
  font-size: 12px;
}

@media (max-width: 1380px) {
  .dashboard-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1050px) {
  .dashboard-main-grid,
  .dashboard-work-grid,
  .dashboard-bottom-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .dashboard-hero :deep(.el-card__body) {
    align-items: flex-start;
    flex-direction: column;
  }

  .dashboard-metrics {
    grid-template-columns: 1fr;
  }

  .hero-actions {
    width: 100%;
    align-items: stretch;
    flex-direction: column;
  }

  .work-row {
    grid-template-columns: 36px 1fr 18px;
  }

  .work-owner,
  .work-row > .el-tag:nth-of-type(2) {
    display: none;
  }
}
</style>
