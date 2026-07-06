export type Severity = "阻断" | "严重" | "一般" | "提示";
export type Status = "待处理" | "进行中" | "已完成" | "已确认" | "已锁定" | "待审核" | "已归档";

export interface NavItem {
  route: string;
  label: string;
  count?: string;
}

export interface NavGroup {
  title: string;
  items: NavItem[];
}

export interface WorkflowStep {
  no: number;
  name: string;
  sub: string;
  route: string;
}

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
  storagePath?: string;
  fileSize?: number;
  mimeType?: string;
  checksum?: string;
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
  storagePath?: string;
  fileSize?: number;
  generatedAt?: string;
}

export interface AppUser {
  id: string;
  name: string;
  role: string;
  department: string;
  status: "启用" | "停用";
  email?: string;
}

export interface ReportTemplate {
  id: string;
  name: string;
  reportType: string;
  version: string;
  status: "草稿" | "已发布" | "已停用";
  updatedAt: string;
}

export interface KnowledgeItem {
  id: string;
  title: string;
  category: string;
  source: string;
  status: "有效" | "待复核" | "停用";
}

export interface AuditLog {
  id: number;
  actor: string;
  action: string;
  entityType: string;
  entityId?: string;
  createdAt: string;
}

export interface QualityRule {
  id: string;
  code: string;
  name: string;
  severity: Severity;
  target: "fact" | "chapter" | "artifact";
  enabled: boolean;
  description: string;
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

export interface DocumentChunk {
  id: string;
  documentId: string;
  projectId: string;
  chunkIndex: number;
  content: string;
  locator: string;
}

export interface BootstrapPayload {
  navGroups: NavGroup[];
  workflow: WorkflowStep[];
  routeMeta: Record<string, [string, string]>;
  projects: Project[];
  documents: ProjectDocument[];
  facts: FactItem[];
  chapters: ReportChapter[];
  qualityIssues: QualityIssue[];
  artifacts: Artifact[];
  users: AppUser[];
  templates: ReportTemplate[];
  knowledgeItems: KnowledgeItem[];
  auditLogs: AuditLog[];
  qualityRules: QualityRule[];
  citations: ChapterCitation[];
  documentChunks: DocumentChunk[];
}

export const navGroups: NavGroup[] = [
  {
    title: "项目作业",
    items: [
      { route: "dashboard", label: "工作台", count: "7" },
      { route: "projects", label: "项目中心" },
      { route: "documents", label: "资料中心", count: "2" },
      { route: "facts", label: "事实与指标", count: "3" },
      { route: "report", label: "编制工作台" }
    ]
  },
  {
    title: "分析与决策",
    items: [
      { route: "analysis", label: "GIS与投资测算" },
      { route: "comparison", label: "方案决策与收敛", count: "后续" },
      { route: "quality", label: "质量、审查与变更", count: "5" },
      { route: "artifacts", label: "成果中心" }
    ]
  },
  {
    title: "能力支撑",
    items: [
      { route: "knowledge", label: "知识与模板" },
      { route: "system", label: "系统管理" }
    ]
  }
];

export const workflow: WorkflowStep[] = [
  { no: 1, name: "项目建档", sub: "范围与权限", route: "projects" },
  { no: 2, name: "资料清点", sub: "版本与完整性", route: "documents" },
  { no: 3, name: "事实确认", sub: "统一数据底板", route: "facts" },
  { no: 4, name: "章节编制", sub: "初稿与引用", route: "report" },
  { no: 5, name: "分析测算", sub: "GIS与投资", route: "analysis" },
  { no: 6, name: "专业复核", sub: "会签与门禁", route: "quality" },
  { no: 7, name: "成果输出", sub: "发布与归档", route: "artifacts" }
];

export const routeMeta: Record<string, [string, string]> = {
  dashboard: ["工作台", "聚合跨项目任务、审核门禁、解析任务和风险提醒"],
  projects: ["项目中心", "项目建档、项目成员、里程碑与项目级配置"],
  documents: ["资料中心", "统一管理项目资料、版本、权限、解析状态和缺失清单"],
  facts: ["事实与指标", "维护项目唯一可信事实底板、指标口径和变更影响"],
  report: ["编制工作台", "按章节组织生成、编辑、引用、校核、审核和跨成果复用"],
  analysis: ["GIS与投资测算", "开展可复现的区域分析、指标测算、投资估算和情景分析"],
  comparison: ["方案决策与收敛", "第三阶段完善候选发散、筛选、评价、推荐和冻结闭环"],
  quality: ["质量、审查与变更", "执行一致性检查、专业会签、决策门禁和发布控制"],
  artifacts: ["成果中心", "生成报告、测算表、决策记录和项目归档包"],
  knowledge: ["知识与模板", "管理政策、案例、规范摘要、报告模板和审查规则"],
  system: ["系统管理", "维护组织权限、模型网关、数据源、安全和审计日志"]
};

export const projects: Project[] = [
  {
    id: "P001",
    name: "蓟州区孙各庄乡村振兴示范项目",
    type: "可行性研究报告",
    location: "天津市蓟州区",
    phase: "MVP样本复现",
    owner: "吴佳宁",
    progress: 68,
    risk: "严重"
  },
  {
    id: "P002",
    name: "老旧小区公共服务设施改造项目",
    type: "项目建议书",
    location: "北京市朝阳区",
    phase: "资料归集",
    owner: "李静",
    progress: 34,
    risk: "一般"
  }
];

export const documents: ProjectDocument[] = [
  { id: "D1", projectId: "P001", name: "项目建议书批复.pdf", category: "批复依据", version: "v1.0", parseStatus: "已解析", source: "业主提供", updatedAt: "2026-07-01" },
  { id: "D2", projectId: "P001", name: "可研基础资料汇编.docx", category: "基础资料", version: "v2.1", parseStatus: "需复核", source: "咨询团队", updatedAt: "2026-07-02" },
  { id: "D3", projectId: "P001", name: "用地红线及现状地形图.pdf", category: "空间资料", version: "v1.2", parseStatus: "已解析", source: "规划部门", updatedAt: "2026-07-01" },
  { id: "D4", projectId: "P001", name: "投资估算模型_v5.xlsx", category: "测算模型", version: "v5.0", parseStatus: "已解析", source: "造价专业", updatedAt: "2026-07-02" },
  { id: "D5", projectId: "P002", name: "小区现状摸排表.xlsx", category: "基础资料", version: "v1.0", parseStatus: "解析中", source: "街道办", updatedAt: "2026-07-03" }
];

export const facts: FactItem[] = [
  { id: "F1", projectId: "P001", group: "项目基本信息", name: "建设地点", value: "天津市蓟州区孙各庄乡", source: "项目建议书批复.pdf 第2页", owner: "王建国", status: "已锁定" },
  { id: "F2", projectId: "P001", group: "投资指标", name: "项目总投资", value: "12800", unit: "万元", source: "投资估算模型_v5.xlsx 汇总表", owner: "赵敏", status: "已确认" },
  { id: "F3", projectId: "P001", group: "建设规模", name: "游客服务中心建筑面积", value: "3200", unit: "平方米", source: "可研基础资料汇编.docx 第4章", owner: "陈志伟", status: "有冲突" },
  { id: "F4", projectId: "P001", group: "资金筹措", name: "专项债资金占比", value: "65", unit: "%", source: "资金平衡测算表", owner: "赵敏", status: "待确认" }
];

export const chapters: ReportChapter[] = [
  { id: "C1", projectId: "P001", no: "1", title: "总论", owner: "吴佳宁", status: "已审核", citationCount: 8, quality: "提示" },
  { id: "C2", projectId: "P001", no: "2", title: "项目建设背景与必要性", owner: "李静", status: "编制中", citationCount: 12, quality: "一般" },
  { id: "C3", projectId: "P001", no: "3", title: "市场与需求分析", owner: "王建国", status: "待审核", citationCount: 9, quality: "严重" },
  { id: "C4", projectId: "P001", no: "4", title: "项目选址与建设条件", owner: "陈志伟", status: "编制中", citationCount: 6, quality: "一般" },
  { id: "C7", projectId: "P001", no: "7", title: "投资估算与资金筹措", owner: "赵敏", status: "待审核", citationCount: 14, quality: "阻断" }
];

export const qualityIssues: QualityIssue[] = [
  { id: "Q1", projectId: "P001", severity: "阻断", type: "数字一致性", title: "总投资与附表金额不一致", owner: "赵敏", status: "待处理" },
  { id: "Q2", projectId: "P001", severity: "严重", type: "引用缺失", title: "市场预测结论缺少政策或案例来源", owner: "李静", status: "处理中" },
  { id: "Q3", projectId: "P001", severity: "一般", type: "事实冲突", title: "游客服务中心面积存在两个口径", owner: "陈志伟", status: "待处理" },
  { id: "Q4", projectId: "P001", severity: "提示", type: "格式规则", title: "章节标题层级需统一", owner: "吴佳宁", status: "已关闭" }
];

export const artifacts: Artifact[] = [
  { id: "A1", projectId: "P001", name: "可行性研究报告.docx", format: "Word", status: "受阻", updatedAt: "2026-07-03" },
  { id: "A2", projectId: "P001", name: "投资估算附表.xlsx", format: "Excel", status: "已生成", updatedAt: "2026-07-02" },
  { id: "A3", projectId: "P001", name: "项目归档包.zip", format: "Archive", status: "可生成", updatedAt: "2026-07-03" }
];

export const users: AppUser[] = [
  { id: "U1", name: "吴佳宁", role: "项目负责人", department: "工程咨询部", status: "启用", email: "owner@zhujian.local" },
  { id: "U2", name: "李静", role: "编制人员", department: "策划研究组", status: "启用", email: "editor@zhujian.local" },
  { id: "U3", name: "赵敏", role: "专业审核人", department: "投资测算组", status: "启用", email: "reviewer@zhujian.local" },
  { id: "U4", name: "系统管理员", role: "管理员", department: "平台运维", status: "启用", email: "admin@zhujian.local" }
];

export const templates: ReportTemplate[] = [
  { id: "RT1", name: "政府投资项目可行性研究报告模板", reportType: "可行性研究报告", version: "v1.0", status: "已发布", updatedAt: "2026-07-03" },
  { id: "RT2", name: "项目建议书通用模板", reportType: "项目建议书", version: "v0.9", status: "草稿", updatedAt: "2026-07-03" }
];

export const knowledgeItems: KnowledgeItem[] = [
  { id: "K1", title: "政府投资项目可行性研究报告编写通用要求", category: "政策规范", source: "知识库导入", status: "有效" },
  { id: "K2", title: "天津市乡村振兴全面推进行动方案", category: "地方政策", source: "资料解析", status: "有效" },
  { id: "K3", title: "乡村旅游服务设施配置历史案例", category: "历史案例", source: "脱敏项目", status: "待复核" }
];

export const auditLogs: AuditLog[] = [];
export const qualityRules: QualityRule[] = [
  { id: "QR1", code: "FACT_CONFLICT", name: "事实冲突检查", severity: "严重", target: "fact", enabled: true, description: "存在有冲突状态的事实时追加严重问题。" },
  { id: "QR2", code: "LOW_CITATION", name: "章节引用不足", severity: "一般", target: "chapter", enabled: true, description: "章节引用数量低于 3 时提示补充依据。" },
  { id: "QR3", code: "BLOCK_EXPORT", name: "阻断问题发布门禁", severity: "阻断", target: "artifact", enabled: true, description: "未关闭阻断问题存在时禁止成果生成。" }
];
export const citations: ChapterCitation[] = [];
export const documentChunks: DocumentChunk[] = [];

export const bootstrap: BootstrapPayload = {
  navGroups,
  workflow,
  routeMeta,
  projects,
  documents,
  facts,
  chapters,
  qualityIssues,
  artifacts,
  users,
  templates,
  knowledgeItems,
  auditLogs,
  qualityRules,
  citations,
  documentChunks
};
