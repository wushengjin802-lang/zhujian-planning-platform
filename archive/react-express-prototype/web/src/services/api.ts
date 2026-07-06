import {
  bootstrap,
  type Artifact,
  type AppUser,
  type BootstrapPayload,
  type FactItem,
  type Project,
  type ProjectDocument,
  type QualityIssue,
  type ReportChapter
} from "@zhujian/shared";

const tokenKey = "zhujian.sessionToken";

export function getStoredToken() {
  return window.localStorage.getItem(tokenKey);
}

export function storeToken(token: string) {
  window.localStorage.setItem(tokenKey, token);
}

export function clearToken() {
  window.localStorage.removeItem(tokenKey);
}

export async function loadBootstrap(): Promise<BootstrapPayload> {
  try {
    const response = await fetch("/api/bootstrap");
    if (!response.ok) throw new Error(`Bootstrap failed: ${response.status}`);
    return (await response.json()) as BootstrapPayload;
  } catch {
    return bootstrap;
  }
}

async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getStoredToken();
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers
    }
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function login(email: string, password: string) {
  const session = await apiRequest<{ token: string; user: AppUser }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password })
  });
  storeToken(session.token);
  return session.user;
}

export async function logout() {
  try {
    await apiRequest<{ ok: boolean }>("/api/auth/logout", { method: "POST" });
  } finally {
    clearToken();
  }
}

export function getCurrentUser() {
  return apiRequest<AppUser>("/api/auth/me");
}

export function createProject(input: { name: string; type?: string; location?: string; owner?: string }) {
  return apiRequest<Project>("/api/projects", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export function createDocument(projectId: string, input: { name: string; category?: string; version?: string; source?: string }) {
  return apiRequest<ProjectDocument>(`/api/projects/${projectId}/documents`, {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export async function uploadDocument(projectId: string, file: File, category = "上传资料") {
  const form = new FormData();
  form.append("file", file);
  form.append("category", category);
  const token = getStoredToken();
  const response = await fetch(`/api/projects/${projectId}/documents/upload`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: form
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Upload failed: ${response.status}`);
  }
  return (await response.json()) as ProjectDocument;
}

export function updateFact(id: string, input: Partial<Pick<FactItem, "value" | "unit" | "source" | "owner" | "status">>) {
  return apiRequest<FactItem>(`/api/facts/${id}`, {
    method: "PATCH",
    body: JSON.stringify(input)
  });
}

export function updateChapter(id: string, input: Partial<Pick<ReportChapter, "status">> & { content?: string }) {
  return apiRequest<ReportChapter>(`/api/chapters/${id}`, {
    method: "PATCH",
    body: JSON.stringify(input)
  });
}

export function generateChapterDraft(id: string) {
  return apiRequest<{ chapter: ReportChapter; content: string }>(`/api/chapters/${id}/generate`, {
    method: "POST"
  });
}

export function updateQualityIssue(id: string, status: QualityIssue["status"]) {
  return apiRequest<QualityIssue>(`/api/quality-issues/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status })
  });
}

export function requestArtifactExport(id: string) {
  return apiRequest<Artifact>(`/api/artifacts/${id}/export`, {
    method: "POST"
  });
}

export function createParseJob(documentId: string) {
  return apiRequest<{ id: string; status: string; message: string }>("/api/documents/parse-jobs", {
    method: "POST",
    body: JSON.stringify({ documentId })
  });
}

export function runDocumentParse(documentId: string) {
  return apiRequest<{ job: { id: string; status: string }; document: ProjectDocument }>(`/api/documents/${documentId}/parse`, {
    method: "POST"
  });
}

export function createQualityCheckJob(projectId: string) {
  return apiRequest<{ id: string; status: string; message: string }>("/api/quality/checks", {
    method: "POST",
    body: JSON.stringify({ projectId })
  });
}
