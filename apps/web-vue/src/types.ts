export type Severity = "阻断" | "严重" | "一般" | "提示";

export interface Project {
  id: string;
  code?: string;
  name: string;
  type: string;
  location: string;
  phase: string;
  owner: string;
  status?: string;
  confidentiality?: string;
  templateId?: string | null;
  templateVersion?: string | null;
  plannedStart?: string | null;
  plannedEnd?: string | null;
  description?: string | null;
  progress: number;
  risk: Severity;
  archivedAt?: string | null;
}

export interface ProjectMemberInfo {
  projectId: string;
  userId: string;
  name: string;
  email?: string | null;
  department?: string | null;
  userStatus?: string | null;
  role: string;
}

export interface ProjectMilestoneInfo {
  id: string;
  projectId: string;
  name: string;
  owner: string;
  status: "未开始" | "进行中" | "已完成" | "已逾期" | string;
  dueAt?: string | null;
  completedAt?: string | null;
  sortOrder: number;
}

export interface ProjectMaterialRequirement {
  id: string;
  projectId: string;
  category: string;
  name: string;
  required: boolean;
  status: "待上传" | "已上传" | "已确认" | "不适用" | string;
  sourceType?: string | null;
  sourceId?: string | null;
  sortOrder: number;
}

export interface ProjectInitializationCheck {
  key: string;
  label: string;
  passed: boolean;
  value?: unknown;
  required?: unknown;
}

export interface ProjectInitializationRecord {
  id: string;
  projectId: string;
  packageVersion: string;
  status: string;
  summary: Record<string, unknown>;
  createdBy?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface ProjectStatusGateItem {
  code: string;
  message: string;
  count?: number;
}

export interface ProjectStatusGate {
  targetStatus: string;
  currentStatus: string;
  allowed: boolean;
  blockers: ProjectStatusGateItem[];
  warnings: ProjectStatusGateItem[];
  checks: Array<{ key: string; label: string; passed: boolean; count?: number }>;
  dryRun?: boolean;
}

export interface ProjectStats {
  documents: number;
  parsedDocuments: number;
  facts: number;
  confirmedFacts: number;
  chapters: number;
  approvedChapters: number;
  openIssues: number;
  blockingIssues: number;
  artifacts: number;
  generatedArtifacts: number;
  members: number;
  milestones: number;
  completedMilestones: number;
  materialRequirements?: number;
  requiredMaterials?: number;
  completedRequiredMaterials?: number;
  severeIssues?: number;
}

export interface ProjectInitialization {
  hasMembers: boolean;
  hasMilestones: boolean;
  hasTemplate: boolean;
  hasDocuments: boolean;
  hasMaterialList?: boolean;
  hasFactFrame?: boolean;
  hasChapterOutline?: boolean;
  hasArtifactPlan?: boolean;
  ready: boolean;
  packageReady?: boolean;
  materialUploadReady?: boolean;
  confirmedFacts?: number;
  requiredMaterials?: number;
  completedRequiredMaterials?: number;
  checks?: ProjectInitializationCheck[];
  missing?: ProjectInitializationCheck[];
  packageVersion?: string;
}

export interface ProjectSummary extends Project {
  createdAt?: string | null;
  updatedAt?: string | null;
  stats: ProjectStats;
  initialization: ProjectInitialization;
  initializationRecord?: ProjectInitializationRecord | null;
  statusGate?: ProjectStatusGate;
}

export interface ProjectProfile extends ProjectSummary {
  members: ProjectMemberInfo[];
  milestones: ProjectMilestoneInfo[];
  materialRequirements?: ProjectMaterialRequirement[];
  initializationRecords?: ProjectInitializationRecord[];
  statusGates?: { close?: ProjectStatusGate; archive?: ProjectStatusGate };
  actions?: {
    canEdit?: boolean;
    canInitialize?: boolean;
    canClose?: boolean;
    canArchive?: boolean;
    canReopen?: boolean;
    canCopy?: boolean;
  };
}

export interface ProjectCenterMetric {
  key: string;
  label: string;
  value: number;
  tone: DashboardTone;
}

export interface ProjectCenterPayload {
  generatedAt: string;
  metrics: ProjectCenterMetric[];
  projects: ProjectSummary[];
  templates: Array<{ id: string; name: string; reportType: string; version: string; status: string }>;
  users: AppUser[];
  statuses: string[];
  confidentialityLevels: string[];
  capabilities: Record<string, boolean>;
}

export interface ProjectCreateInput {
  name: string;
  type?: string;
  location?: string;
  owner?: string;
  code?: string;
  templateId?: string;
  templateVersion?: string;
  confidentiality?: string;
  plannedStart?: string;
  plannedEnd?: string;
  description?: string;
  members?: Array<{ userId: string; role: string }>;
  milestones?: Array<{ name: string; owner?: string; status?: string; dueAt?: string; sortOrder?: number }>;
}

export interface ProjectDocument {
  id: string;
  projectId: string;
  name: string;
  category: string;
  version: string;
  parseStatus: "待解析" | "解析中" | "已解析" | "需复核";
  source: string;
  updatedAt: string;
  fileSize?: number;
  chunkCount?: number;
}

export interface FactItem {
  id: string;
  projectId: string;
  group: string;
  name: string;
  value: string;
  unit?: string;
  source: string;
  owner: string;
  status: "待确认" | "已确认" | "已锁定" | "有冲突";
}

export interface ReportChapter {
  id: string;
  projectId: string;
  no: string;
  title: string;
  owner: string;
  status: "未开始" | "编制中" | "待审核" | "已审核";
  citationCount: number;
  quality: Severity;
}

export interface QualityIssue {
  id: string;
  projectId: string;
  severity: Severity;
  type: string;
  title: string;
  owner: string;
  status: "待处理" | "处理中" | "已关闭";
}

export interface Artifact {
  id: string;
  projectId: string;
  name: string;
  format: "Word" | "Excel" | "PPT" | "Archive";
  status: "可生成" | "生成中" | "已生成" | "受阻";
  updatedAt: string;
}

export interface AppUser {
  id: string;
  name: string;
  role: string;
  department: string;
  status: "启用" | "停用";
  email?: string;
}

export interface ChapterCitation {
  id: string;
  chapterId: string;
  factId?: string;
  documentId?: string;
  chunkId?: string;
  excerpt: string;
  source: string;
}

export interface BootstrapPayload {
  navGroups: Array<{ title: string; items: Array<{ route: string; label: string; count?: string }> }>;
  workflow: Array<{ no: number; name: string; sub: string; route: string }>;
  routeMeta: Record<string, [string, string]>;
  projects: Project[];
  documents: ProjectDocument[];
  facts: FactItem[];
  chapters: ReportChapter[];
  qualityIssues: QualityIssue[];
  artifacts: Artifact[];
  users: AppUser[];
  templates: Array<{ id: string; name: string; reportType: string; version: string; status: string; updatedAt: string }>;
  knowledgeItems: Array<{ id: string; title: string; category: string; source: string; status: string }>;
  auditLogs: Array<{ id: number; actor: string; action: string; entityType: string; entityId?: string; createdAt: string }>;
  qualityRules: Array<{ id: string; code: string; name: string; severity: Severity; target: string; enabled: boolean; description: string }>;
  citations: ChapterCitation[];
  documentChunks: Array<{ id: string; projectId: string; documentId: string; chunkIndex: number; content: string; locator: string }>;
}

export interface InvestmentBreakdown {
  category: string;
  ratio: number;
  amount: string;
  amount_raw: number;
}

export interface UnitMetric {
  area: string;
  unitInv: string;
  unitInvRaw: number;
}

export interface FundingItem {
  ratio: number;
  amount: string;
}

export interface EstimateOutput {
  totalInvestment: string;
  totalInvestmentRaw: number;
  breakdown: InvestmentBreakdown[];
  unitMetrics: Record<string, UnitMetric>;
  funding: Record<string, FundingItem>;
}

export interface SensitivityItem {
  scenario: string;
  delta: number;
  totalVariant: string;
  changePct: string;
  changePctRaw: number;
}

export interface InvestmentEstimate {
  id: string;
  projectId: string;
  status: "draft" | "calculated" | "confirmed";
  inputSnapshot: Record<string, string>;
  output: EstimateOutput;
  sensitivity: SensitivityItem[];
  confirmedBy: string | null;
  confirmedAt: string | null;
  createdAt: string;
}

export interface PlatformStatus {
  database: {
    connected: boolean;
    schema: string;
    extensions: Record<string, { available: boolean; installed: boolean; installedVersion?: string | null; defaultVersion?: string | null }>;
  };
  redis: { available: boolean; url: string; message?: string };
  minio: { available: boolean; endpoint: string; bucket: string; message?: string };
  libreOffice: { available: boolean; binary?: string | null; message?: string };
  modelGateway: { configured: boolean; available: boolean; mode: string; message?: string };
}

export type DashboardTone = "primary" | "success" | "warning" | "danger" | "info";

export interface DashboardMetric {
  key: string;
  label: string;
  value: number;
  unit: string;
  description: string;
  tone: DashboardTone;
  route: string;
}

export interface DashboardWorkflowItem {
  key: string;
  name: string;
  done: number;
  total: number;
  percentage: number;
  route: string;
}

export interface DashboardProjectSummary {
  id: string;
  name: string;
  type: string;
  phase: string;
  owner: string;
  location: string;
  progress: number;
  risk: Severity;
  documents: string;
  facts: string;
  chapters: string;
  openIssues: number;
}

export type DashboardDueStatus = "none" | "normal" | "due_soon" | "overdue";
export type DashboardSlaLevel = "none" | "normal" | "warning" | "critical";

export interface DashboardCardHealth {
  key: string;
  label: string;
  status: "normal" | "warning" | "danger" | "degraded" | "empty" | string;
  count: number;
  alerts: number;
  message: string;
}

export interface DashboardSlaSummary {
  overdue: number;
  dueSoon: number;
  normal: number;
  total: number;
  level: "normal" | "warning" | "danger";
  message: string;
}

export interface DashboardWorkItem {
  id: string;
  category: string;
  title: string;
  projectId?: string | null;
  projectName: string;
  owner: string;
  assigneeId?: string | null;
  assigneeName?: string | null;
  priority: "P0" | "P1" | "P2" | "P3";
  status: string;
  route: string;
  detail: string;
  dueAt?: string | null;
  dueStatus?: DashboardDueStatus;
  dueHoursRemaining?: number | null;
  slaLevel?: DashboardSlaLevel;
  slaLabel?: string;
  sourceType?: string | null;
  sourceId?: string | null;
  persistent?: boolean;
  actions?: {
    canClaim?: boolean;
    canComplete?: boolean;
    canTransfer?: boolean;
    canCancel?: boolean;
    canComment?: boolean;
    canViewEvents?: boolean;
  };
  actionReasons?: Record<string, string>;
}

export interface DashboardReviewItem {
  id: string;
  type: string;
  title: string;
  projectId?: string | null;
  projectName: string;
  submitter: string;
  reviewerId?: string | null;
  reviewerName?: string | null;
  priority: "P0" | "P1" | "P2" | "P3";
  status: string;
  route: string;
  description: string;
  targetType?: string;
  targetId?: string;
  decision?: string | null;
  comment?: string | null;
  dueAt?: string | null;
  dueStatus?: DashboardDueStatus;
  dueHoursRemaining?: number | null;
  slaLevel?: DashboardSlaLevel;
  slaLabel?: string;
  persistent?: boolean;
  actions?: {
    canAssign?: boolean;
    canApprove?: boolean;
    canReject?: boolean;
    canComment?: boolean;
    canCountersign?: boolean;
    canViewEvents?: boolean;
  };
  actionReasons?: Record<string, string>;
  countersign?: {
    required: number;
    signed: number;
    remaining: number;
    gatePassed: boolean;
    signers: string[];
    label: string;
  };
}

export interface DashboardTask {
  id: string;
  taskKind: "parse" | "quality" | "artifact";
  type: string;
  name: string;
  projectId?: string | null;
  projectName: string;
  status: string;
  rawStatus?: string;
  message: string;
  progress: number;
  updatedAt?: string | null;
  route: string;
  stuck?: boolean;
  stuckMinutes?: number | null;
  heartbeat?: { level: "normal" | "warning" | "danger" | "unknown" | string; message: string; minutesSinceUpdate?: number | null };
  canCancel?: boolean;
  canRetry?: boolean;
}

export interface DashboardNotification {
  id: string;
  level: DashboardTone;
  title: string;
  message: string;
  route: string;
  status?: string;
  projectId?: string | null;
  sourceType?: string | null;
  sourceId?: string | null;
  createdAt?: string | null;
}

export interface WorkbenchEvent {
  id: string;
  projectId?: string | null;
  targetType: string;
  targetId: string;
  action: string;
  actorId?: string | null;
  actorName: string;
  comment?: string | null;
  payload: Record<string, unknown>;
  createdAt?: string | null;
}

export interface TaskEvent {
  id: string;
  projectId?: string | null;
  taskKind: "parse" | "quality" | "artifact" | string;
  taskId: string;
  status: string;
  stage: string;
  message: string;
  actorId?: string | null;
  actorName?: string | null;
  payload: Record<string, unknown>;
  createdAt?: string | null;
}

export interface DashboardActivity {
  id: string;
  actor: string;
  action: string;
  entityType: string;
  entityId?: string | null;
  createdAt: string;
  detail: Record<string, unknown>;
}

export interface NotificationSubscription {
  eventType: string;
  label: string;
  enabled: boolean;
  delivery: string;
  updatedAt?: string | null;
}

export interface DashboardPayload {
  generatedAt: string;
  scope: "project" | "all";
  roleMode: "personal" | "management";
  user: AppUser;
  metrics: DashboardMetric[];
  workflow: DashboardWorkflowItem[];
  projects: DashboardProjectSummary[];
  workItems: DashboardWorkItem[];
  reviewQueue: DashboardReviewItem[];
  tasks: DashboardTask[];
  notifications: DashboardNotification[];
  slaSummary?: DashboardSlaSummary;
  cardHealth?: DashboardCardHealth[];
  cardErrors?: Array<{ card: string; message: string; level: string }>;
  latestEvents: WorkbenchEvent[];
  taskEvents: TaskEvent[];
  recentActivities: DashboardActivity[];
  quickActions: Array<{ key: string; label: string; description: string; route: string }>;
  capabilities?: Record<string, boolean>;
}
