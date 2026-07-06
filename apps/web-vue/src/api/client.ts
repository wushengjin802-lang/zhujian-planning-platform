import type { AppUser, Artifact, BootstrapPayload, DashboardNotification, DashboardPayload, FactItem, InvestmentEstimate, NotificationSubscription, PlatformStatus, Project, ProjectCenterPayload, ProjectCreateInput, ProjectDocument, ProjectProfile, QualityIssue, ReportChapter, TaskEvent, WorkbenchEvent } from "../types";

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

export function loadProjectCenter() {
  return request<ProjectCenterPayload>("/api/project-center");
}

export function loadProjectProfile(projectId: string) {
  return request<ProjectProfile>(`/api/projects/${projectId}`);
}

export function createProject(input: ProjectCreateInput) {
  return request<ProjectProfile>("/api/projects", { method: "POST", body: JSON.stringify(input) });
}

export function updateProject(projectId: string, input: Partial<ProjectCreateInput> & { phase?: string; progress?: number; risk?: string }) {
  return request<ProjectProfile>(`/api/projects/${projectId}`, { method: "PATCH", body: JSON.stringify(input) });
}

export function addProjectMember(projectId: string, input: { userId: string; role: string }) {
  return request<ProjectProfile>(`/api/projects/${projectId}/members`, { method: "POST", body: JSON.stringify(input) });
}

export function removeProjectMember(projectId: string, userId: string) {
  return request<ProjectProfile>(`/api/projects/${projectId}/members/${userId}`, { method: "DELETE" });
}

export function addProjectMilestone(projectId: string, input: { name: string; owner?: string; status?: string; dueAt?: string; sortOrder?: number }) {
  return request<ProjectProfile>(`/api/projects/${projectId}/milestones`, { method: "POST", body: JSON.stringify(input) });
}

export function updateProjectMilestone(projectId: string, milestoneId: string, input: { name: string; owner?: string; status?: string; dueAt?: string; sortOrder?: number }) {
  return request<ProjectProfile>(`/api/projects/${projectId}/milestones/${milestoneId}`, { method: "PATCH", body: JSON.stringify(input) });
}

export function changeProjectStatus(projectId: string, status: string, reason?: string) {
  return request<ProjectProfile>(`/api/projects/${projectId}/status`, { method: "POST", body: JSON.stringify({ status, reason }) });
}

export function copyProject(projectId: string, input: { name?: string; copyMembers?: boolean; copyMilestones?: boolean; copySettings?: boolean }) {
  return request<ProjectProfile>(`/api/projects/${projectId}/copy`, { method: "POST", body: JSON.stringify(input) });
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

export function transferWorkItem(id: string, assigneeId: string, comment?: string) {
  return request<{ id: string; status: string; assigneeId?: string }>(`/api/work-items/${id}/transfer`, {
    method: "POST",
    body: JSON.stringify({ assigneeId, comment })
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

export function cancelBackgroundTask(id: string, taskKind: "parse" | "quality" | "artifact", force = false) {
  return request<{ id: string; taskKind: string; status: string; force?: boolean }>(`/api/tasks/${id}/cancel`, {
    method: "POST",
    body: JSON.stringify({ taskKind, force })
  });
}

export function retryBackgroundTask(id: string, taskKind: "parse" | "quality" | "artifact") {
  return request<{ id: string; taskKind: string; status: string }>(`/api/tasks/${id}/retry`, {
    method: "POST",
    body: JSON.stringify({ taskKind })
  });
}


export function cancelWorkItem(id: string, comment?: string) {
  return request<{ id: string; status: string }>(`/api/work-items/${id}/cancel`, {
    method: "POST",
    body: JSON.stringify({ comment })
  });
}

export function commentWorkItem(id: string, comment: string) {
  return request<WorkbenchEvent>(`/api/work-items/${id}/comments`, {
    method: "POST",
    body: JSON.stringify({ comment })
  });
}

export function loadWorkItemEvents(id: string) {
  return request<WorkbenchEvent[]>(`/api/work-items/${id}/events`);
}

export function commentReviewTask(id: string, comment: string) {
  return request<WorkbenchEvent>(`/api/review-tasks/${id}/comments`, {
    method: "POST",
    body: JSON.stringify({ comment })
  });
}

export function assignReviewTask(id: string, reviewerId: string, comment?: string) {
  return request<{ id: string; status: string; reviewerId: string }>(`/api/review-tasks/${id}/assign`, {
    method: "POST",
    body: JSON.stringify({ reviewerId, comment })
  });
}

export function countersignReviewTask(id: string, comment?: string) {
  return request<WorkbenchEvent>(`/api/review-tasks/${id}/countersign`, {
    method: "POST",
    body: JSON.stringify({ comment })
  });
}

export function loadReviewTaskEvents(id: string) {
  return request<WorkbenchEvent[]>(`/api/review-tasks/${id}/events`);
}

export function listNotifications(status?: string, projectId?: string) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (projectId) params.set("projectId", projectId);
  const query = params.toString();
  return request<DashboardNotification[]>(`/api/notifications${query ? `?${query}` : ""}`);
}

export function listNotificationSubscriptions() {
  return request<NotificationSubscription[]>("/api/notification-subscriptions");
}

export function updateNotificationSubscription(eventType: string, enabled: boolean, delivery = "in_app") {
  return request<NotificationSubscription>(`/api/notification-subscriptions/${encodeURIComponent(eventType)}`, {
    method: "PUT",
    body: JSON.stringify({ enabled, delivery })
  });
}

export function markNotificationsReadAll(projectId?: string) {
  return request<{ count: number; status: string }>("/api/notifications/read-all", {
    method: "POST",
    body: JSON.stringify({ projectId })
  });
}

export function archiveNotification(id: string) {
  return request<{ id: string; status: string }>(`/api/notifications/${id}/archive`, { method: "POST" });
}

export function loadTaskEvents(id: string, taskKind: "parse" | "quality" | "artifact") {
  return request<TaskEvent[]>(`/api/tasks/${id}/events?taskKind=${encodeURIComponent(taskKind)}`);
}
