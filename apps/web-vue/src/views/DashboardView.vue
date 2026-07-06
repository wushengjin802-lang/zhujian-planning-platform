<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { ElMessageBox } from "element-plus";
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
import type { DashboardMetric, DashboardTone, WorkbenchEvent } from "../types";
import { usePlatformStore } from "../stores/platform";

const store = usePlatformStore();
const router = useRouter();
const activeWorkTab = ref<"todo" | "review">("todo");
const taskFilter = ref("全部");
const activeActivityTab = ref<"audit" | "event">("audit");
const eventDialogVisible = ref(false);
const eventDialogTitle = ref("处理记录");
const eventRows = ref<WorkbenchEvent[]>([]);
const eventLoading = ref(false);

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

async function promptComment(title: string, placeholder: string) {
  const result = await ElMessageBox.prompt(placeholder, title, {
    confirmButtonText: "提交",
    cancelButtonText: "取消",
    inputType: "textarea",
    inputPlaceholder: placeholder
  });
  return result.value;
}

async function commentWorkItem(id: string) {
  const comment = await promptComment("补充工作项意见", "请输入处理意见、问题说明或下一步安排");
  await store.commentDashboardWorkItem(id, comment);
}

async function cancelWorkItem(id: string) {
  const comment = await promptComment("取消工作项", "请输入取消原因");
  await store.cancelDashboardWorkItem(id, comment);
}

async function commentReviewTask(id: string) {
  const comment = await promptComment("补充审核意见", "请输入审核意见");
  await store.commentDashboardReviewTask(id, comment);
}

async function countersignReviewTask(id: string) {
  const comment = await promptComment("审核会签", "请输入会签意见");
  await store.countersignDashboardReviewTask(id, comment);
}

async function assignReviewTask(id: string) {
  const result = await ElMessageBox.prompt("请输入审核人用户ID，例如 U001", "分配审核人", {
    confirmButtonText: "分配",
    cancelButtonText: "取消",
    inputPlaceholder: "审核人用户ID"
  });
  await store.assignDashboardReviewTask(id, result.value, "工作台分配审核人");
}

async function transferWorkItemAction(id: string) {
  const result = await ElMessageBox.prompt("请输入接收人用户ID，例如 U001", "转交工作项", {
    confirmButtonText: "转交",
    cancelButtonText: "取消",
    inputPlaceholder: "接收人用户ID"
  });
  await store.transferDashboardWorkItem(id, result.value, "工作台转交");
}

function eventActionLabel(action: string) {
  const labels: Record<string, string> = {
    claim: "领取",
    complete: "完成",
    transfer: "转交",
    cancel: "取消",
    comment: "意见",
    assign: "分配",
    countersign: "会签",
    approve: "通过",
    reject: "退回"
  };
  return labels[action] ?? action;
}

function dueLabel(dueStatus?: string, dueAt?: string | null) {
  if (!dueAt || dueStatus === "none") return "";
  const prefix = dueStatus === "overdue" ? "已逾期" : dueStatus === "due_soon" ? "即将到期" : "截止";
  return `${prefix} ${formatTime(dueAt)}`;
}

function dueType(dueStatus?: string) {
  if (dueStatus === "overdue") return "danger";
  if (dueStatus === "due_soon") return "warning";
  if (dueStatus === "normal") return "info";
  return "info";
}

function healthType(status?: string) {
  if (status === "danger") return "danger";
  if (status === "warning" || status === "degraded") return "warning";
  if (status === "normal") return "success";
  return "info";
}

function slaSummaryText() {
  const summary = dashboard.value?.slaSummary;
  if (!summary || !summary.total) return "暂无SLA风险";
  return summary.message;
}

async function showWorkItemEvents(id: string, title: string) {
  eventDialogTitle.value = `工作项记录：${title}`;
  eventDialogVisible.value = true;
  eventLoading.value = true;
  try {
    eventRows.value = await store.loadWorkItemEvents(id);
  } finally {
    eventLoading.value = false;
  }
}

async function showReviewTaskEvents(id: string, title: string) {
  eventDialogTitle.value = `审核记录：${title}`;
  eventDialogVisible.value = true;
  eventLoading.value = true;
  try {
    eventRows.value = await store.loadReviewTaskEvents(id);
  } finally {
    eventLoading.value = false;
  }
}

function taskEventsFor(row: { id: string; taskKind: string }) {
  return (dashboard.value?.taskEvents ?? []).filter((item) => item.taskId === row.id && item.taskKind === row.taskKind).slice(0, 3);
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

      <section class="dashboard-health-row">
        <el-card class="dashboard-panel health-card" shadow="never">
          <template #header>
            <div class="dashboard-panel-title">
              <div>
                <h3>工作台健康状态</h3>
                <p>{{ slaSummaryText() }}</p>
              </div>
              <el-tag :type="dashboard.slaSummary?.level === 'danger' ? 'danger' : dashboard.slaSummary?.level === 'warning' ? 'warning' : 'success'">SLA</el-tag>
            </div>
          </template>
          <div class="health-grid">
            <div v-for="card in dashboard.cardHealth ?? []" :key="card.key" class="health-item">
              <el-tag :type="healthType(card.status)" effect="plain" size="small">{{ card.label }}</el-tag>
              <strong>{{ card.count }}</strong>
              <span>{{ card.message }}<em v-if="card.alerts"> · {{ card.alerts }} 项需关注</em></span>
            </div>
          </div>
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
              <div class="header-actions">
                <el-button size="small" link type="primary" @click="store.readAllDashboardNotifications(store.dashboardScope === 'current' ? store.currentProject?.id : undefined)">全部已读</el-button>
                <el-icon class="header-icon"><BellFilled /></el-icon>
              </div>
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
            <span v-if="notice.id !== 'all-clear' && notice.id !== 'stuck-tasks'" class="notice-actions">
              <el-button link type="primary" @click.stop="store.readDashboardNotification(notice.id)">已读</el-button>
              <el-button link type="info" @click.stop="store.archiveDashboardNotification(notice.id)">归档</el-button>
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
                <el-tag v-if="dueLabel(item.dueStatus, item.dueAt)" :type="dueType(item.dueStatus)" effect="plain" size="small">{{ item.slaLabel || dueLabel(item.dueStatus, item.dueAt) }}</el-tag>
              </span>
              <span class="work-owner">{{ item.assigneeName || item.owner }}</span>
              <el-tag :type="statusType(item.status)" effect="plain" size="small">{{ item.status }}</el-tag>
              <span class="work-actions">
                <el-button v-if="item.actions?.canClaim" link type="primary" @click.stop="store.claimDashboardWorkItem(item.id)">领取</el-button>
                <el-button v-if="item.actions?.canComment" link type="info" @click.stop="commentWorkItem(item.id)">意见</el-button>
                <el-button v-if="item.actions?.canTransfer" link type="primary" @click.stop="transferWorkItemAction(item.id)">转交</el-button>
                <el-button v-if="item.actions?.canComplete" link type="success" @click.stop="store.completeDashboardWorkItem(item.id)">完成</el-button>
                <el-button v-if="item.actions?.canCancel" link type="warning" @click.stop="cancelWorkItem(item.id)">取消</el-button>
                <el-button v-if="item.actions?.canViewEvents !== false" link type="info" @click.stop="showWorkItemEvents(item.id, item.title)">记录</el-button>
              </span>
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
                <el-tag v-if="dueLabel(item.dueStatus, item.dueAt)" :type="dueType(item.dueStatus)" effect="plain" size="small">{{ item.slaLabel || dueLabel(item.dueStatus, item.dueAt) }}</el-tag>
              </span>
              <span class="work-owner">{{ item.reviewerName || item.submitter }}</span>
              <el-tag type="warning" effect="plain" size="small">{{ item.status }}</el-tag>
              <span class="work-actions">
                <el-button v-if="item.actions?.canAssign" link type="primary" @click.stop="assignReviewTask(item.id)">分配</el-button>
                <el-button v-if="item.actions?.canComment" link type="info" @click.stop="commentReviewTask(item.id)">意见</el-button>
                <el-button v-if="item.actions?.canApprove" link type="success" @click.stop="store.approveDashboardReviewTask(item.id)">通过</el-button>
                <el-button v-if="item.actions?.canReject" link type="warning" @click.stop="store.rejectDashboardReviewTask(item.id)">退回</el-button>
                <el-button v-if="item.actions?.canCountersign" link type="primary" @click.stop="countersignReviewTask(item.id)">会签</el-button>
                <el-button v-if="item.actions?.canViewEvents !== false" link type="info" @click.stop="showReviewTaskEvents(item.id, item.title)">记录</el-button>
              </span>
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
            <el-table-column type="expand" width="38">
              <template #default="{ row }">
                <div class="task-event-list">
                  <strong>阶段日志</strong>
                  <p v-for="event in taskEventsFor(row)" :key="event.id">{{ formatTime(event.createdAt) }} · {{ event.stage }} · {{ event.message }}</p>
                  <p v-if="!taskEventsFor(row).length">暂无阶段日志</p>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="任务" min-width="210">
              <template #default="{ row }">
                <div class="task-name">
                  <strong>{{ row.name }}</strong>
                  <span>{{ row.type }} · {{ row.projectName }} · {{ row.heartbeat?.message || row.message }}</span>
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
                <el-tag :type="row.stuck ? 'danger' : statusType(row.status)" size="small">{{ row.stuck ? `疑似卡住${row.stuckMinutes ? ' ' + row.stuckMinutes + '分钟' : ''}` : row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="更新时间" width="120">
              <template #default="{ row }">{{ formatTime(row.updatedAt) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="145" align="right">
              <template #default="{ row }">
                <el-button v-if="row.canCancel" link type="warning" @click="store.cancelDashboardTask(row.id, row.taskKind)">取消</el-button>
                <el-button v-if="row.canRetry || row.stuck" link type="danger" @click="store.retryDashboardTask(row.id, row.taskKind)">重试</el-button>
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
                <p>审计记录与工作台处理留痕</p>
              </div>
              <el-tabs v-model="activeActivityTab" class="activity-tabs">
                <el-tab-pane label="审计" name="audit" />
                <el-tab-pane label="事件" name="event" />
              </el-tabs>
            </div>
          </template>
          <el-timeline v-if="activeActivityTab === 'audit'">
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
          <el-timeline v-else>
            <el-timeline-item
              v-for="event in dashboard.latestEvents.slice(0, 7)"
              :key="event.id"
              :timestamp="formatTime(event.createdAt)"
              placement="top"
            >
              <strong>{{ event.action }}</strong>
              <p>{{ event.actorName }} · {{ event.comment || '无补充意见' }}</p>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-if="activeActivityTab === 'audit' && !dashboard.recentActivities.length" description="暂无活动记录" :image-size="70" />
          <el-empty v-if="activeActivityTab === 'event' && !dashboard.latestEvents.length" description="暂无工作台事件" :image-size="70" />
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

      <el-dialog v-model="eventDialogVisible" :title="eventDialogTitle" width="560px">
        <el-timeline v-loading="eventLoading" class="event-dialog-timeline">
          <el-timeline-item
            v-for="event in eventRows"
            :key="event.id"
            :timestamp="formatTime(event.createdAt)"
            placement="top"
          >
            <strong>{{ eventActionLabel(event.action) }}</strong>
            <p>{{ event.actorName }} · {{ event.comment || '无补充意见' }}</p>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-if="!eventLoading && !eventRows.length" description="暂无处理记录" :image-size="70" />
      </el-dialog>
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

.header-actions,
.notice-actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.activity-tabs :deep(.el-tabs__header) {
  margin: 0;
}

.task-event-list {
  margin: 4px 16px 8px 54px;
  padding: 12px 14px;
  border-radius: 8px;
  background: #f7faf9;
}

.task-event-list strong {
  display: block;
  margin-bottom: 6px;
  color: #203746;
}

.task-event-list p {
  margin: 3px 0;
  color: #667985;
  font-size: 12px;
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
  grid-template-columns: 30px 1fr auto 20px;
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
  grid-template-columns: 38px minmax(0, 1fr) 95px 82px 188px 18px;
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

.work-actions {
  display: inline-flex;
  justify-content: flex-end;
  gap: 4px;
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
  .work-actions,
  .work-row > .el-tag:nth-of-type(2) {
    display: none;
  }
}
.event-dialog-timeline {
  min-height: 80px;
  max-height: 420px;
  overflow: auto;
  padding-right: 8px;
}

.event-dialog-timeline p {
  margin: 4px 0 0;
  color: #64748b;
}

.dashboard-health-row {
  display: grid;
  grid-template-columns: 1fr;
}

.health-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}

.health-item {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid rgba(23, 63, 91, 0.1);
  border-radius: 12px;
  background: #f8fbfd;
}

.health-item strong {
  color: #173f5b;
  font-size: 22px;
}

.health-item span {
  color: #617386;
  font-size: 12px;
}

.health-item em {
  color: #b65d0b;
  font-style: normal;
}

</style>
