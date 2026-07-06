import type { AppUser, Artifact, BootstrapPayload, DashboardPayload, FactItem, InvestmentEstimate, PlatformStatus, Project, ProjectDocument, QualityIssue, ReportChapter } from "../types";

const tokenKey = "zhujian.sessionToken";

export function getStoredToken() {
  return window.localStorage.getItem(tokenKey);
}

export function clearToken() {
  window.localStorage.removeItem(tokenKey);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getStoredToken();
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers
    }
  });
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()) as T;
}

export function loadBootstrap() {
  return request<BootstrapPayload>("/api/bootstrap");
}

export function loadPlatformStatus() {
  return request<PlatformStatus>("/api/platform/status");
}

export function loadDashboard(projectId?: string) {
  const query = projectId ? `?projectId=${encodeURIComponent(projectId)}` : "";
  return request<DashboardPayload>(`/api/dashboard${query}`);
}

export async function login(email: string, password: string) {
  const session = await request<{ token: string; user: AppUser }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password })
  });
  window.localStorage.setItem(tokenKey, session.token);
  return session.user;
}

export function getCurrentUser() {
  return request<AppUser>("/api/auth/me");
}

export async function logout() {
  try {
    await request<{ ok: boolean }>("/api/auth/logout", { method: "POST" });
  } finally {
    clearToken();
  }
}

export function createProject(input: { name: string; type?: string; location?: string; owner?: string }) {
  return request<Project>("/api/projects", { method: "POST", body: JSON.stringify(input) });
}

export function createDocument(projectId: string, input: { name: string; category?: string; version?: string; source?: string }) {
  return request<ProjectDocument>(`/api/projects/${projectId}/documents`, { method: "POST", body: JSON.stringify(input) });
}

export async function uploadDocument(projectId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  const token = getStoredToken();
  const response = await fetch(`/api/projects/${projectId}/documents/upload`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: form
  });
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()) as ProjectDocument;
}

export function updateFact(id: string, input: Partial<Pick<FactItem, "value" | "unit" | "source" | "owner" | "status">>) {
  return request<FactItem>(`/api/facts/${id}`, { method: "PATCH", body: JSON.stringify(input) });
}

export function updateChapter(id: string, input: Partial<Pick<ReportChapter, "status">> & { content?: string }) {
  return request<ReportChapter>(`/api/chapters/${id}`, { method: "PATCH", body: JSON.stringify(input) });
}

export function generateChapterDraft(id: string) {
  return request<{ chapter: ReportChapter; content: string }>(`/api/chapters/${id}/generate`, { method: "POST" });
}

export function updateQualityIssue(id: string, status: QualityIssue["status"]) {
  return request<QualityIssue>(`/api/quality-issues/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });
}

export function requestArtifactExport(id: string) {
  return request<Artifact>(`/api/artifacts/${id}/export`, { method: "POST" });
}

export function runDocumentParse(documentId: string) {
  return request<{ job: { id: string; status: string }; document: ProjectDocument; chunks: number }>(`/api/documents/${documentId}/parse`, { method: "POST" });
}

export function createQualityCheckJob(projectId: string) {
  return request<{ id: string; status: string; message: string }>("/api/quality/checks", { method: "POST", body: JSON.stringify({ projectId }) });
}

export function loadInvestmentEstimate(projectId: string) {
  return request<InvestmentEstimate>(`/api/estimates/${projectId}`);
}

export function calculateInvestmentEstimate(projectId: string) {
  return request<InvestmentEstimate>(`/api/estimates/${projectId}/calculate`, { method: "POST" });
}

export function confirmInvestmentEstimate(estimateId: string) {
  return request<InvestmentEstimate>(`/api/estimates/${estimateId}/confirm`, { method: "POST" });
}


export function claimWorkItem(id: string, assigneeId?: string) {
  return request<{ id: string; status: string; assigneeId?: string }>(`/api/work-items/${id}/claim`, {
    method: "POST",
    body: JSON.stringify({ assigneeId })
  });
}

export function completeWorkItem(id: string, comment?: string) {
  return request<{ id: string; status: string }>(`/api/work-items/${id}/complete`, {
    method: "POST",
    body: JSON.stringify({ comment })
  });
}

export function approveReviewTask(id: string, comment?: string) {
  return request<{ id: string; status: string; decision: string }>(`/api/review-tasks/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ comment })
  });
}

export function rejectReviewTask(id: string, comment?: string) {
  return request<{ id: string; status: string; decision: string; comment?: string }>(`/api/review-tasks/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ comment })
  });
}

export function markNotificationRead(id: string) {
  return request<{ id: string; status: string }>(`/api/notifications/${id}/read`, { method: "POST" });
}

export function cancelBackgroundTask(id: string, taskKind: "parse" | "quality" | "artifact") {
  return request<{ id: string; taskKind: string; status: string }>(`/api/tasks/${id}/cancel`, {
    method: "POST",
    body: JSON.stringify({ taskKind })
  });
}

export function retryBackgroundTask(id: string, taskKind: "parse" | "quality" | "artifact") {
  return request<{ id: string; taskKind: string; status: string }>(`/api/tasks/${id}/retry`, {
    method: "POST",
    body: JSON.stringify({ taskKind })
  });
}
