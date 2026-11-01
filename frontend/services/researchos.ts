import { API_BASE_URL, apiFetch, apiStreamNdjson, apiUpload, toQueryString } from "@/lib/api";
import type {
  Analysis,
  AnalysisCreate,
  AnalysisKind,
  AskEvent,
  AssistantStatus,
  AttachmentOptions,
  ChatScope,
  ChatSession,
  ChatSessionDetail,
  CitationStyle,
  ChunkPage,
  Collection,
  DashboardSummary,
  DocumentDetail,
  DocumentFilters,
  DocumentPage,
  DocumentUpdate,
  FormattedCitation,
  GraphData,
  LibraryFacets,
  LiteratureReview,
  PaperProfile,
  Project,
  ProjectInput,
  ProjectStatus,
  ReviewSummary,
  SystemStatus,
  Tag,
} from "@/types/api";

const json = (method: string, body: unknown): RequestInit => ({
  method,
  body: JSON.stringify(body),
});

export const dashboardService = {
  get: () => apiFetch<DashboardSummary>("/api/dashboard"),
};

export const systemService = {
  status: () => apiFetch<SystemStatus>("/api/system/status"),
};

export const projectService = {
  list: (status?: ProjectStatus) =>
    apiFetch<Project[]>(`/api/projects${status ? `?status=${status}` : ""}`),
  create: (input: ProjectInput) => apiFetch<Project>("/api/projects", json("POST", input)),
  update: (id: number, input: Partial<ProjectInput>) =>
    apiFetch<Project>(`/api/projects/${id}`, json("PATCH", input)),
  remove: (id: number) => apiFetch<void>(`/api/projects/${id}`, { method: "DELETE" }),
};

export const documentService = {
  list: (filters: DocumentFilters) =>
    apiFetch<DocumentPage>(`/api/documents${toQueryString(filters)}`),
  get: (id: number) => apiFetch<DocumentDetail>(`/api/documents/${id}`),
  upload: (
    file: File,
    options: AttachmentOptions,
    onProgress?: (fraction: number) => void,
    signal?: AbortSignal,
  ) => {
    const form = new FormData();
    form.append("file", file);
    form.append("options", JSON.stringify(options));
    return apiUpload<DocumentDetail>("/api/documents/upload", form, onProgress, signal);
  },
  importUrl: (url: string, options: AttachmentOptions) =>
    apiFetch<DocumentDetail>("/api/documents/url", json("POST", { url, ...options })),
  createNote: (title: string, body: string, options: AttachmentOptions) =>
    apiFetch<DocumentDetail>("/api/documents/notes", json("POST", { title, body, ...options })),
  update: (id: number, input: DocumentUpdate) =>
    apiFetch<DocumentDetail>(`/api/documents/${id}`, json("PATCH", input)),
  remove: (id: number) => apiFetch<void>(`/api/documents/${id}`, { method: "DELETE" }),
  setTags: (id: number, names: string[]) =>
    apiFetch<DocumentDetail>(`/api/documents/${id}/tags`, json("PUT", { names })),
  setCollections: (id: number, ids: number[]) =>
    apiFetch<DocumentDetail>(`/api/documents/${id}/collections`, json("PUT", { ids })),
  setProjects: (id: number, ids: number[]) =>
    apiFetch<DocumentDetail>(`/api/documents/${id}/projects`, json("PUT", { ids })),
  chunks: (id: number, params: { offset?: number; limit?: number; page?: number }) =>
    apiFetch<ChunkPage>(`/api/documents/${id}/chunks${toQueryString(params)}`),
  fileUrl: (id: number) => `${API_BASE_URL}/api/documents/${id}/file`,
};

export const libraryService = {
  facets: () => apiFetch<LibraryFacets>("/api/library/facets"),
};

export const collectionService = {
  list: () => apiFetch<Collection[]>("/api/collections"),
  create: (name: string, description?: string | null) =>
    apiFetch<Collection>("/api/collections", json("POST", { name, description })),
  update: (id: number, input: { name?: string; description?: string | null }) =>
    apiFetch<Collection>(`/api/collections/${id}`, json("PATCH", input)),
  remove: (id: number) => apiFetch<void>(`/api/collections/${id}`, { method: "DELETE" }),
};

export const tagService = {
  list: () => apiFetch<Tag[]>("/api/tags"),
  remove: (id: number) => apiFetch<void>(`/api/tags/${id}`, { method: "DELETE" }),
};

export const assistantService = {
  status: () => apiFetch<AssistantStatus>("/api/assistant/status"),
  updateSettings: (input: { chat_provider?: string; cloud_consent?: boolean }) =>
    apiFetch<AssistantStatus>("/api/assistant/settings", json("PUT", input)),
  reindex: (documentIds: number[] = []) =>
    apiFetch<{ queued: number }>("/api/assistant/reindex", json("POST", { document_ids: documentIds })),
  sessions: () => apiFetch<ChatSession[]>("/api/assistant/sessions"),
  session: (id: number) => apiFetch<ChatSessionDetail>(`/api/assistant/sessions/${id}`),
  createSession: (scope?: ChatScope) =>
    apiFetch<ChatSession>("/api/assistant/sessions", json("POST", { scope })),
  renameSession: (id: number, title: string) =>
    apiFetch<ChatSession>(`/api/assistant/sessions/${id}`, json("PATCH", { title })),
  deleteSession: (id: number) => apiFetch<void>(`/api/assistant/sessions/${id}`, { method: "DELETE" }),
  ask: (
    sessionId: number,
    content: string,
    scope: ChatScope | undefined,
    onEvent: (event: AskEvent) => void,
    signal?: AbortSignal,
  ) =>
    apiStreamNdjson<AskEvent>(
      `/api/assistant/sessions/${sessionId}/messages`,
      { content, scope },
      onEvent,
      signal,
    ),
};

export const analysisService = {
  create: (input: AnalysisCreate) => apiFetch<Analysis>("/api/analyses", json("POST", input)),
  list: (params: { kind?: AnalysisKind; document_id?: number; limit?: number }) =>
    apiFetch<Analysis[]>(`/api/analyses${toQueryString(params)}`),
  get: (id: number) => apiFetch<Analysis>(`/api/analyses/${id}`),
  cancel: (id: number) => apiFetch<Analysis>(`/api/analyses/${id}/cancel`, { method: "POST" }),
  rerun: (id: number) => apiFetch<Analysis>(`/api/analyses/${id}/rerun`, { method: "POST" }),
  remove: (id: number) => apiFetch<void>(`/api/analyses/${id}`, { method: "DELETE" }),
  profile: (documentId: number) => apiFetch<PaperProfile>(`/api/documents/${documentId}/profile`),
  reportDownloadUrl: (reportId: number) => `${API_BASE_URL}/api/reports/${reportId}/download`,
};

export const citationService = {
  styles: () => apiFetch<Record<CitationStyle, string>>("/api/citations/styles"),
  list: (style: CitationStyle, documentIds?: number[]) =>
    apiFetch<FormattedCitation[]>(`/api/citations${toQueryString({ style, document_id: documentIds })}`),
  exportUrl: (format: "bibtex" | "ris" | "markdown" | "text", style: CitationStyle, documentIds?: number[]) =>
    `${API_BASE_URL}/api/citations/export${toQueryString({ format, style, document_id: documentIds })}`,
};

export const graphService = {
  get: (params: { include?: string[]; collection_id?: number; project_id?: number; similarity?: number }) =>
    apiFetch<GraphData>(`/api/graph${toQueryString(params)}`),
  paper: (documentId: number) => apiFetch<GraphData>(`/api/graph/papers/${documentId}`),
};

export const reviewService = {
  list: () => apiFetch<ReviewSummary[]>("/api/reviews"),
  get: (id: number) => apiFetch<LiteratureReview>(`/api/reviews/${id}`),
  create: (input: { title: string; research_question?: string | null; project_id?: number | null }) =>
    apiFetch<LiteratureReview>("/api/reviews", json("POST", input)),
  update: (id: number, input: Partial<Pick<LiteratureReview, "title" | "research_question" | "introduction" | "citation_style">>) =>
    apiFetch<LiteratureReview>(`/api/reviews/${id}`, json("PATCH", input)),
  remove: (id: number) => apiFetch<void>(`/api/reviews/${id}`, { method: "DELETE" }),
  addTheme: (id: number, input: { name: string; description?: string | null; document_ids?: number[] }) =>
    apiFetch<LiteratureReview>(`/api/reviews/${id}/themes`, json("POST", input)),
  updateTheme: (themeId: number, input: { name?: string; description?: string | null; position?: number }) =>
    apiFetch<LiteratureReview>(`/api/reviews/themes/${themeId}`, json("PATCH", input)),
  removeTheme: (themeId: number) => apiFetch<void>(`/api/reviews/themes/${themeId}`, { method: "DELETE" }),
  setItems: (themeId: number, items: { document_id: number; note?: string | null }[]) =>
    apiFetch<LiteratureReview>(`/api/reviews/themes/${themeId}/items`, json("PUT", { items })),
  suggest: (id: number, documentIds: number[]) =>
    apiFetch<{ groups: { name: string; document_ids: number[] }[]; unindexed_document_ids: number[]; method: string }>(
      `/api/reviews/${id}/suggest-themes`,
      json("POST", { document_ids: documentIds }),
    ),
  summarise: (themeId: number) => apiFetch<LiteratureReview>(`/api/reviews/themes/${themeId}/summary`, { method: "POST" }),
  exportUrl: (id: number, style?: CitationStyle) => `${API_BASE_URL}/api/reviews/${id}/export${toQueryString({ style })}`,
};
