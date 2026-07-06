export type Severity = "阻断" | "严重" | "一般" | "提示";

export interface Project {
  id: string;
  name: string;
  type: string;
  location: string;
  phase: string;
  owner: string;
  progress: number;
  risk: Severity;
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

export interface DashboardWorkItem {
  id: string;
  category: string;
  title: string;
  projectId: string;
  projectName: string;
  owner: string;
  priority: "P0" | "P1" | "P2" | "P3";
  status: string;
  route: string;
  detail: string;
}

export interface DashboardReviewItem {
  id: string;
  type: string;
  title: string;
  projectId: string;
  projectName: string;
  submitter: string;
  priority: "P0" | "P1" | "P2" | "P3";
  status: string;
  route: string;
  description: string;
}

export interface DashboardTask {
  id: string;
  type: string;
  name: string;
  projectId?: string | null;
  projectName: string;
  status: string;
  message: string;
  progress: number;
  updatedAt?: string | null;
  route: string;
}

export interface DashboardNotification {
  id: string;
  level: DashboardTone;
  title: string;
  message: string;
  route: string;
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
  recentActivities: DashboardActivity[];
  quickActions: Array<{ key: string; label: string; description: string; route: string }>;
}
