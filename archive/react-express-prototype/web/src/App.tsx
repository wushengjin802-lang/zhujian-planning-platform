import { useEffect, useMemo, useState } from "react";
import type * as React from "react";
import {
  Archive,
  BarChart3,
  Bell,
  BookOpen,
  Boxes,
  CheckCircle2,
  ChevronRight,
  CircleCheck,
  ClipboardCheck,
  Database,
  FilePlus2,
  FileSpreadsheet,
  FileText,
  FolderKanban,
  Gauge,
  History,
  LayoutDashboard,
  Library,
  LockKeyhole,
  MapPinned,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  PlayCircle,
  UploadCloud,
  Users
} from "lucide-react";
import type {
  Artifact,
  AppUser,
  BootstrapPayload,
  FactItem,
  ProjectDocument,
  QualityIssue,
  ReportChapter,
  Severity
} from "@zhujian/shared";
import { bootstrap } from "@zhujian/shared";
import {
  createDocument,
  createProject,
  createQualityCheckJob,
  generateChapterDraft,
  getCurrentUser,
  loadBootstrap,
  login,
  logout,
  requestArtifactExport,
  runDocumentParse,
  updateChapter,
  updateFact,
  updateQualityIssue,
  uploadDocument
} from "./services/api";

type Route =
  | "dashboard"
  | "projects"
  | "documents"
  | "facts"
  | "report"
  | "analysis"
  | "comparison"
  | "quality"
  | "artifacts"
  | "knowledge"
  | "system";

const routeIcons: Record<Route, React.ElementType> = {
  dashboard: LayoutDashboard,
  projects: FolderKanban,
  documents: UploadCloud,
  facts: Database,
  report: FileText,
  analysis: MapPinned,
  comparison: BarChart3,
  quality: ClipboardCheck,
  artifacts: Archive,
  knowledge: Library,
  system: Settings
};

const severityClass: Record<Severity, string> = {
  阻断: "danger",
  严重: "warning",
  一般: "notice",
  提示: "muted"
};

interface ActionHandlers {
  createProject: () => void;
  registerDocument: () => void;
  uploadDocument: () => void;
  startParseJob: (documentId: string) => void;
  confirmFact: (fact: FactItem) => void;
  lockFact: (fact: FactItem) => void;
  resolveFactConflict: (fact: FactItem) => void;
  submitChapter: (chapter: ReportChapter) => void;
  approveChapter: (chapter: ReportChapter) => void;
  generateChapter: (chapter: ReportChapter) => void;
  runQualityCheck: () => void;
  closeIssue: (issue: QualityIssue) => void;
  exportArtifact: (artifact: Artifact) => void;
}

export function App() {
  const [data, setData] = useState<BootstrapPayload>(bootstrap);
  const [route, setRoute] = useState<Route>("dashboard");
  const [projectId, setProjectId] = useState("P001");
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState("已连接 PostgreSQL");
  const [currentUser, setCurrentUser] = useState<AppUser | null>(null);

  useEffect(() => {
    loadBootstrap().then((payload) => {
      setData(payload);
      setLoading(false);
    });
    getCurrentUser().then(setCurrentUser).catch(() => setCurrentUser(null));
  }, []);

  const currentProject = data.projects.find((project) => project.id === projectId) ?? data.projects[0];
  const projectDocuments = data.documents.filter((item) => item.projectId === currentProject.id);
  const projectFacts = data.facts.filter((item) => item.projectId === currentProject.id);
  const projectChapters = data.chapters.filter((item) => item.projectId === currentProject.id);
  const projectIssues = data.qualityIssues.filter((item) => item.projectId === currentProject.id);
  const projectArtifacts = data.artifacts.filter((item) => item.projectId === currentProject.id);
  const [title, subtitle] = data.routeMeta[route];

  const metrics = useMemo(
    () => [
      { label: "资料解析完成率", value: percent(projectDocuments.filter((item) => item.parseStatus === "已解析").length, projectDocuments.length), icon: UploadCloud },
      { label: "事实确认率", value: percent(projectFacts.filter((item) => item.status === "已确认" || item.status === "已锁定").length, projectFacts.length), icon: ShieldCheck },
      { label: "章节审核进度", value: percent(projectChapters.filter((item) => item.status === "已审核").length, projectChapters.length), icon: FileText },
      { label: "阻断问题", value: String(projectIssues.filter((item) => item.severity === "阻断").length), icon: LockKeyhole }
    ],
    [projectChapters, projectDocuments, projectFacts, projectIssues]
  );

  async function refreshData() {
    const payload = await loadBootstrap();
    setData(payload);
    if (!payload.projects.some((project) => project.id === projectId) && payload.projects[0]) {
      setProjectId(payload.projects[0].id);
    }
  }

  async function runAction(label: string, operation: () => Promise<unknown>) {
    if (!currentUser) {
      setNotice("请先登录后再执行写入操作");
      return;
    }
    setLoading(true);
    try {
      await operation();
      await refreshData();
      setNotice(`${label}完成`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : `${label}失败`);
    } finally {
      setLoading(false);
    }
  }

  const actions: ActionHandlers = {
    createProject: () => {
      const name = window.prompt("项目名称", "新建可研样本项目");
      if (!name) return;
      const location = window.prompt("项目地点", "待补充") ?? "待补充";
      runAction("项目建档", async () => {
        const project = await createProject({ name, location, owner: "项目负责人" });
        setProjectId(project.id);
      });
    },
    registerDocument: () => {
      const name = window.prompt("资料名称", "新上传资料.pdf");
      if (!name) return;
      const category = window.prompt("资料分类", "基础资料") ?? "基础资料";
      runAction("资料登记", () => createDocument(currentProject.id, { name, category, source: "人工登记" }));
    },
    uploadDocument: () => {
      const input = window.document.createElement("input");
      input.type = "file";
      input.onchange = () => {
        const file = input.files?.[0];
        if (!file) return;
        runAction("资料上传", () => uploadDocument(currentProject.id, file));
      };
      input.click();
    },
    startParseJob: (documentId) => runAction("资料解析", () => runDocumentParse(documentId)),
    confirmFact: (fact) => runAction("事实确认", () => updateFact(fact.id, { status: "已确认" })),
    lockFact: (fact) => runAction("事实锁定", () => updateFact(fact.id, { status: "已锁定" })),
    resolveFactConflict: (fact) => {
      const value = window.prompt("确认后的事实值", fact.value);
      if (!value) return;
      runAction("事实冲突处理", () => updateFact(fact.id, { value, status: "已确认" }));
    },
    submitChapter: (chapter) => runAction("章节提交审核", () => updateChapter(chapter.id, { status: "待审核" })),
    approveChapter: (chapter) => runAction("章节审核", () => updateChapter(chapter.id, { status: "已审核" })),
    generateChapter: (chapter) => runAction("章节初稿生成", () => generateChapterDraft(chapter.id)),
    runQualityCheck: () => runAction("质量检查", () => createQualityCheckJob(currentProject.id)),
    closeIssue: (issue) => runAction("质量问题关闭", () => updateQualityIssue(issue.id, "已关闭")),
    exportArtifact: (artifact) => runAction("成果导出请求", () => requestArtifactExport(artifact.id))
  };

  async function handleLogin() {
    const email = window.prompt("登录邮箱", "owner@zhujian.local");
    if (!email) return;
    const password = window.prompt("密码", "demo123");
    if (!password) return;
    setLoading(true);
    try {
      const user = await login(email, password);
      setCurrentUser(user);
      await refreshData();
      setNotice(`已登录：${user.name}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleLogout() {
    await logout();
    setCurrentUser(null);
    setNotice("已退出登录");
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">策</div>
          <div>
            <strong>住建智策</strong>
            <span>工程咨询辅助编制平台</span>
          </div>
        </div>

        <div className="project-chip">
          <span>当前项目</span>
          <strong>{currentProject.name}</strong>
          <small>{currentProject.type} · {currentProject.phase}</small>
        </div>

        <nav className="main-nav">
          {data.navGroups.map((group) => (
            <section key={group.title}>
              <h2>{group.title}</h2>
              {group.items.map((item) => {
                const typedRoute = item.route as Route;
                const Icon = routeIcons[typedRoute];
                return (
                  <button
                    className={route === typedRoute ? "active" : ""}
                    key={item.route}
                    onClick={() => setRoute(typedRoute)}
                  >
                    <Icon size={18} />
                    <span>{item.label}</span>
                    {item.count ? <em>{item.count}</em> : null}
                  </button>
                );
              })}
            </section>
          ))}
        </nav>

        <div className="sidebar-foot">
          <CheckCircle2 size={16} />
          <span>第一阶段 MVP 开发环境</span>
        </div>
      </aside>

      <main className="main-shell">
        <header className="topbar">
          <div>
            <span className="eyebrow">Phase 1 · MVP 闭环</span>
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
          <div className="topbar-actions">
            <div className="search-box">
              <Search size={16} />
              <span>检索项目、资料、事实、章节</span>
              <kbd>Ctrl K</kbd>
            </div>
            <button className="icon-action" title="消息通知"><Bell size={18} /></button>
            {currentUser ? (
              <button className="user-pill" onClick={handleLogout} title="退出登录">
                <ShieldCheck size={16} />
                <span>{currentUser.name}</span>
              </button>
            ) : (
              <button className="user-pill" onClick={handleLogin} title="登录">
                <ShieldCheck size={16} />
                <span>登录</span>
              </button>
            )}
            <select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
              {data.projects.map((project) => (
                <option value={project.id} key={project.id}>{project.name}</option>
              ))}
            </select>
          </div>
        </header>

        <section className="workflow-strip">
          {data.workflow.map((step) => (
            <button
              key={step.no}
              className={route === step.route ? "active" : ""}
              onClick={() => setRoute(step.route as Route)}
            >
              <span>{step.no}</span>
              <strong>{step.name}</strong>
              <small>{step.sub}</small>
            </button>
          ))}
        </section>

        <div className="loading">{loading ? "正在同步 PostgreSQL 数据..." : notice}</div>

        <section className="page-content">
          {route === "dashboard" && <Dashboard metrics={metrics} project={currentProject} issues={projectIssues} documents={projectDocuments} />}
          {route === "projects" && <Projects projects={data.projects} activeProjectId={projectId} onSelect={setProjectId} onCreate={actions.createProject} />}
          {route === "documents" && <Documents documents={projectDocuments} onRegister={actions.registerDocument} onUpload={actions.uploadDocument} onParse={actions.startParseJob} />}
          {route === "facts" && <Facts facts={projectFacts} onConfirm={actions.confirmFact} onLock={actions.lockFact} onResolve={actions.resolveFactConflict} />}
          {route === "report" && <Report chapters={projectChapters} facts={projectFacts} citations={data.citations} onGenerate={actions.generateChapter} onSubmit={actions.submitChapter} onApprove={actions.approveChapter} />}
          {route === "analysis" && <Analysis />}
          {route === "comparison" && <Comparison />}
          {route === "quality" && <Quality issues={projectIssues} onRunCheck={actions.runQualityCheck} onClose={actions.closeIssue} />}
          {route === "artifacts" && <Artifacts artifacts={projectArtifacts} issues={projectIssues} onExport={actions.exportArtifact} />}
          {route === "knowledge" && <Knowledge templates={data.templates} knowledgeItems={data.knowledgeItems} />}
          {route === "system" && <System users={data.users} auditLogs={data.auditLogs} qualityRules={data.qualityRules} />}
        </section>
      </main>
    </div>
  );
}

function Dashboard({
  metrics,
  project,
  issues,
  documents
}: {
  metrics: Array<{ label: string; value: string; icon: React.ElementType }>;
  project: BootstrapPayload["projects"][number];
  issues: QualityIssue[];
  documents: ProjectDocument[];
}) {
  return (
    <>
      <section className="metric-grid">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <article className="metric-panel" key={metric.label}>
              <Icon size={20} />
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
            </article>
          );
        })}
      </section>

      <section className="split-grid">
        <article className="panel focus-panel">
          <div className="panel-title">
            <Gauge size={18} />
            <h2>MVP 主链路状态</h2>
          </div>
          <div className="project-progress">
            <strong>{project.progress}%</strong>
            <div><span style={{ width: `${project.progress}%` }} /></div>
          </div>
          <p>当前样本项目已进入事实确认与章节编制并行阶段，质量门禁发现 {issues.length} 项待复核问题。</p>
        </article>

        <article className="panel">
          <div className="panel-title">
            <History size={18} />
            <h2>近期任务</h2>
          </div>
          <ul className="task-list">
            <li><span>资料解析</span><strong>{documents.filter((item) => item.parseStatus === "需复核").length} 个文件需复核</strong></li>
            <li><span>事实确认</span><strong>投资与建设规模口径待统一</strong></li>
            <li><span>发布门禁</span><strong>阻断问题关闭后可生成报告</strong></li>
          </ul>
        </article>
      </section>
    </>
  );
}

function Projects({
  projects,
  activeProjectId,
  onSelect,
  onCreate
}: {
  projects: BootstrapPayload["projects"];
  activeProjectId: string;
  onSelect: (id: string) => void;
  onCreate: () => void;
}) {
  return (
    <>
      <PageToolbar title="项目建档" action={<ActionButton icon={FilePlus2} label="新建项目" onClick={onCreate} />} />
      <section className="record-grid">
        {projects.map((project) => (
          <button className={`record-panel ${project.id === activeProjectId ? "selected" : ""}`} key={project.id} onClick={() => onSelect(project.id)}>
            <div className="record-top">
              <FolderKanban size={18} />
              <Badge tone={severityClass[project.risk]}>{project.risk}</Badge>
            </div>
            <h2>{project.name}</h2>
            <p>{project.location} · {project.type}</p>
            <div className="mini-progress"><span style={{ width: `${project.progress}%` }} /></div>
            <small>{project.owner} · {project.phase}</small>
          </button>
        ))}
      </section>
    </>
  );
}

function Documents({
  documents,
  onRegister,
  onUpload,
  onParse
}: {
  documents: ProjectDocument[];
  onRegister: () => void;
  onUpload: () => void;
  onParse: (documentId: string) => void;
}) {
  return (
    <>
      <PageToolbar
        title="资料清点与解析"
        action={
          <InlineActions>
            <ActionButton icon={UploadCloud} label="上传文件" onClick={onUpload} />
            <ActionButton icon={FilePlus2} label="登记资料" onClick={onRegister} />
          </InlineActions>
        }
      />
      <DataTable
        columns={["资料名称", "分类", "版本", "解析状态", "文件/切片", "来源", "更新时间", "操作"]}
        rows={documents.map((item) => [
          item.name,
          item.category,
          item.version,
          <Badge key={item.id} tone={item.parseStatus === "需复核" ? "warning" : item.parseStatus === "解析中" ? "notice" : item.parseStatus === "待解析" ? "muted" : "ok"}>{item.parseStatus}</Badge>,
          `${item.fileSize ? `${Math.round(item.fileSize / 1024)} KB` : "未上传"} / ${item.chunkCount ?? 0}片`,
          item.source,
          item.updatedAt,
          <InlineActions key={item.id}>
            {item.parseStatus !== "已解析" ? <ActionButton icon={PlayCircle} label="解析" onClick={() => onParse(item.id)} compact /> : null}
          </InlineActions>
        ])}
      />
    </>
  );
}

function Facts({
  facts,
  onConfirm,
  onLock,
  onResolve
}: {
  facts: FactItem[];
  onConfirm: (fact: FactItem) => void;
  onLock: (fact: FactItem) => void;
  onResolve: (fact: FactItem) => void;
}) {
  return (
    <DataTable
      columns={["事实项", "分组", "值", "来源", "责任人", "状态", "操作"]}
      rows={facts.map((item) => [
        item.name,
        item.group,
        `${item.value}${item.unit ?? ""}`,
        item.source,
        item.owner,
        <Badge key={item.id} tone={item.status === "有冲突" ? "warning" : item.status === "已锁定" ? "ok" : "notice"}>{item.status}</Badge>,
        <InlineActions key={item.id}>
          {item.status === "有冲突" ? <ActionButton icon={CircleCheck} label="处理冲突" onClick={() => onResolve(item)} compact /> : null}
          {item.status !== "已确认" && item.status !== "已锁定" ? <ActionButton icon={CircleCheck} label="确认" onClick={() => onConfirm(item)} compact /> : null}
          {item.status !== "已锁定" ? <ActionButton icon={LockKeyhole} label="锁定" onClick={() => onLock(item)} compact /> : null}
        </InlineActions>
      ])}
    />
  );
}

function Report({
  chapters,
  facts,
  citations,
  onSubmit,
  onApprove,
  onGenerate
}: {
  chapters: ReportChapter[];
  facts: FactItem[];
  citations: BootstrapPayload["citations"];
  onSubmit: (chapter: ReportChapter) => void;
  onApprove: (chapter: ReportChapter) => void;
  onGenerate: (chapter: ReportChapter) => void;
}) {
  return (
    <section className="editor-layout">
      <aside className="chapter-list">
        {chapters.map((chapter) => (
          <button key={chapter.id}>
            <span>{chapter.no}</span>
            <strong>{chapter.title}</strong>
            <Badge tone={severityClass[chapter.quality]}>{chapter.status}</Badge>
          </button>
        ))}
      </aside>
      <article className="panel editor-panel">
        <div className="panel-title">
          <Sparkles size={18} />
          <h2>章节编制草稿</h2>
        </div>
        <p>
          系统将依据已确认事实、政策规范和模板结构生成章节初稿。当前版本保留 AI 建议入口，
          后续接入模型网关、引用回链和在线批注。
        </p>
        <div className="fact-snippets">
          {facts.slice(0, 3).map((fact) => (
            <span key={fact.id}>{fact.name}: {fact.value}{fact.unit ?? ""}</span>
          ))}
        </div>
        <div className="chapter-actions">
          {chapters.map((chapter) => (
            <div key={chapter.id} className="chapter-action-row">
              <span>{chapter.no}. {chapter.title}</span>
              <InlineActions>
                <ActionButton icon={Sparkles} label="生成初稿" onClick={() => onGenerate(chapter)} compact />
                {chapter.status !== "待审核" && chapter.status !== "已审核" ? <ActionButton icon={PlayCircle} label="提交审核" onClick={() => onSubmit(chapter)} compact /> : null}
                {chapter.status !== "已审核" ? <ActionButton icon={CircleCheck} label="审核通过" onClick={() => onApprove(chapter)} compact /> : null}
              </InlineActions>
            </div>
          ))}
        </div>
        <div className="citation-panel">
          <h3>引用回链</h3>
          {citations.length ? citations.slice(0, 6).map((citation) => (
            <div className="citation-row" key={citation.id}>
              <strong>{citation.excerpt}</strong>
              <span>{citation.source}{citation.chunkId ? ` · ${citation.chunkId}` : ""}</span>
            </div>
          )) : <p>生成章节初稿后将自动形成引用回链。</p>}
        </div>
      </article>
    </section>
  );
}

function Analysis() {
  return (
    <section className="split-grid">
      <article className="panel">
        <div className="panel-title"><MapPinned size={18} /><h2>GIS 区位分析</h2></div>
        <div className="map-placeholder">
          <span>项目范围</span>
          <i className="pin p1" />
          <i className="pin p2" />
          <i className="ring" />
        </div>
      </article>
      <article className="panel">
        <div className="panel-title"><FileSpreadsheet size={18} /><h2>投资测算摘要</h2></div>
        <ul className="task-list">
          <li><span>总投资</span><strong>12,800 万元</strong></li>
          <li><span>专项债资金</span><strong>65%</strong></li>
          <li><span>敏感性</span><strong>运营收入下降 10% 需复核</strong></li>
        </ul>
      </article>
    </section>
  );
}

function Comparison() {
  return (
    <article className="panel focus-panel">
      <div className="panel-title"><Boxes size={18} /><h2>方案决策与收敛</h2></div>
      <p>
        第一阶段保留轻量方案比较入口，用于承接建设方案章节与投资测算结果。完整的目标约束、
        候选方案池、多角色评价、分歧识别和分层冻结将在第三阶段开发。
      </p>
      <div className="milestone-row">
        <Badge tone="notice">候选方案登记</Badge>
        <ChevronRight size={16} />
        <Badge tone="notice">投资与约束校核</Badge>
        <ChevronRight size={16} />
        <Badge tone="muted">第三阶段冻结闭环</Badge>
      </div>
    </article>
  );
}

function Quality({
  issues,
  onRunCheck,
  onClose
}: {
  issues: QualityIssue[];
  onRunCheck: () => void;
  onClose: (issue: QualityIssue) => void;
}) {
  return (
    <>
      <PageToolbar title="质量门禁" action={<ActionButton icon={PlayCircle} label="运行检查" onClick={onRunCheck} />} />
      <DataTable
        columns={["等级", "类型", "问题", "责任人", "状态", "操作"]}
        rows={issues.map((item) => [
          <Badge key={item.id} tone={severityClass[item.severity]}>{item.severity}</Badge>,
          item.type,
          item.title,
          item.owner,
          item.status,
          <InlineActions key={item.id}>
            {item.status !== "已关闭" ? <ActionButton icon={CircleCheck} label="关闭" onClick={() => onClose(item)} compact /> : null}
          </InlineActions>
        ])}
      />
    </>
  );
}

function Artifacts({
  artifacts,
  issues,
  onExport
}: {
  artifacts: Artifact[];
  issues: QualityIssue[];
  onExport: (artifact: Artifact) => void;
}) {
  const blocked = issues.some((item) => item.severity === "阻断" && item.status !== "已关闭");
  return (
    <section className="split-grid">
      <article className="panel">
        <div className="panel-title"><Archive size={18} /><h2>成果清单</h2></div>
        <ul className="artifact-list">
          {artifacts.map((artifact) => (
            <li key={artifact.id}>
              <span>{artifact.name}</span>
              <InlineActions>
                <Badge tone={artifact.status === "受阻" ? "danger" : artifact.status === "已生成" ? "ok" : "notice"}>{artifact.status}</Badge>
                <ActionButton icon={PlayCircle} label="导出" onClick={() => onExport(artifact)} compact />
                {artifact.status === "已生成" ? <a className="download-link" href={`/api/artifacts/${artifact.id}/download`}>下载</a> : null}
              </InlineActions>
            </li>
          ))}
        </ul>
      </article>
      <article className="panel focus-panel">
        <div className="panel-title"><LockKeyhole size={18} /><h2>发布门禁</h2></div>
        <p>{blocked ? "存在未关闭阻断问题，正式成果发布暂不可用。" : "质量门禁已通过，可进入成果发布和归档。"}</p>
      </article>
    </section>
  );
}

function Knowledge({
  templates,
  knowledgeItems
}: {
  templates: BootstrapPayload["templates"];
  knowledgeItems: BootstrapPayload["knowledgeItems"];
}) {
  return (
    <section className="split-grid">
      <article className="panel">
        <div className="panel-title"><BookOpen size={18} /><h2>报告模板</h2></div>
        <ul className="artifact-list">
          {templates.map((template) => (
            <li key={template.id}>
              <span>{template.name}</span>
              <InlineActions>
                <Badge tone={template.status === "已发布" ? "ok" : "notice"}>{template.version}</Badge>
                <Badge tone={template.status === "已发布" ? "ok" : "muted"}>{template.status}</Badge>
              </InlineActions>
            </li>
          ))}
        </ul>
      </article>
      <article className="panel">
        <div className="panel-title"><Library size={18} /><h2>知识条目</h2></div>
        <ul className="artifact-list">
          {knowledgeItems.map((item) => (
            <li key={item.id}>
              <span>{item.title}</span>
              <InlineActions>
                <Badge tone="notice">{item.category}</Badge>
                <Badge tone={item.status === "有效" ? "ok" : "warning"}>{item.status}</Badge>
              </InlineActions>
            </li>
          ))}
        </ul>
      </article>
    </section>
  );
}

function System({
  users,
  auditLogs,
  qualityRules
}: {
  users: BootstrapPayload["users"];
  auditLogs: BootstrapPayload["auditLogs"];
  qualityRules: BootstrapPayload["qualityRules"];
}) {
  return (
    <section className="system-grid">
      <article className="panel">
        <div className="panel-title"><Users size={18} /><h2>组织与角色</h2></div>
        <ul className="artifact-list">
          {users.map((user) => (
            <li key={user.id}>
              <span>{user.name} · {user.department}</span>
              <InlineActions>
                <Badge tone="notice">{user.role}</Badge>
                <Badge tone={user.status === "启用" ? "ok" : "muted"}>{user.status}</Badge>
              </InlineActions>
            </li>
          ))}
        </ul>
      </article>
      <article className="panel">
        <div className="panel-title"><ShieldCheck size={18} /><h2>最近审计</h2></div>
        <ul className="artifact-list">
          {auditLogs.slice(0, 10).map((log) => (
            <li key={log.id}>
              <span>{log.action} · {log.entityType}</span>
              <Badge tone="muted">{log.actor}</Badge>
            </li>
          ))}
        </ul>
      </article>
      <article className="panel">
        <div className="panel-title"><Settings size={18} /><h2>质量规则</h2></div>
        <ul className="artifact-list">
          {qualityRules.map((rule) => (
            <li key={rule.id}>
              <span>{rule.name}</span>
              <InlineActions>
                <Badge tone={severityClass[rule.severity]}>{rule.severity}</Badge>
                <Badge tone={rule.enabled ? "ok" : "muted"}>{rule.enabled ? "启用" : "停用"}</Badge>
              </InlineActions>
            </li>
          ))}
        </ul>
      </article>
    </section>
  );
}

function DataTable({ columns, rows }: { columns: string[]; rows: Array<Array<React.ReactNode>> }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PageToolbar({ title, action }: { title: string; action: React.ReactNode }) {
  return (
    <div className="page-toolbar">
      <strong>{title}</strong>
      {action}
    </div>
  );
}

function InlineActions({ children }: { children: React.ReactNode }) {
  return <div className="inline-actions">{children}</div>;
}

function ActionButton({
  icon: Icon,
  label,
  onClick,
  compact = false
}: {
  icon: React.ElementType;
  label: string;
  onClick: () => void;
  compact?: boolean;
}) {
  return (
    <button className={compact ? "action-button compact" : "action-button"} onClick={onClick}>
      <Icon size={compact ? 14 : 16} />
      <span>{label}</span>
    </button>
  );
}

function Badge({ children, tone }: { children: React.ReactNode; tone: string }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

function percent(done: number, total: number) {
  if (!total) return "0%";
  return `${Math.round((done / total) * 100)}%`;
}
