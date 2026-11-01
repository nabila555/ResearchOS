// Types mirror the backend Pydantic schemas in backend/app/schemas.

export type DocumentType = "pdf" | "docx" | "text" | "markdown" | "web" | "note";
export type DocumentStatus = "pending" | "processing" | "ready" | "failed";
export type ProjectStatus = "active" | "paused" | "completed" | "archived";

export interface Project {
  id: number;
  name: string;
  description: string | null;
  research_question: string | null;
  status: ProjectStatus;
  document_count: number;
  report_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectInput {
  name: string;
  description?: string | null;
  research_question?: string | null;
  status?: ProjectStatus;
}

export interface DashboardStats {
  documents_total: number;
  documents_by_type: Record<DocumentType, number>;
  collections_total: number;
  tags_total: number;
  projects_total: number;
  projects_active: number;
  reports_total: number;
}

export interface RecentDocument {
  id: number;
  title: string;
  doc_type: DocumentType;
  status: DocumentStatus;
  publication_year: number | null;
  created_at: string;
}

export interface TopicCount {
  name: string;
  document_count: number;
}

export interface Activity {
  id: number;
  action: string;
  entity_type: string;
  entity_id: number | null;
  summary: string;
  created_at: string;
}

export interface RecentReport {
  id: number;
  title: string;
  report_type: string;
  created_at: string;
}

export interface DashboardSummary {
  stats: DashboardStats;
  recent_documents: RecentDocument[];
  topics: TopicCount[];
  active_projects: Project[];
  recent_activity: Activity[];
  recent_reports: RecentReport[];
}

export interface OllamaStatus {
  base_url: string;
  reachable: boolean;
  models: string[];
  chat_model: string;
  embed_model: string;
  chat_model_available: boolean;
  embed_model_available: boolean;
  error: string | null;
}

export interface SystemStatus {
  app_name: string;
  version: string;
  environment: string;
  storage: { data_dir: string; database_backend: string; max_upload_mb: number };
  ai: {
    active_provider: string;
    ollama: OllamaStatus;
    anthropic: { configured: boolean; model: string };
  };
}

// --- Research library ---------------------------------------------------------

export interface Ref {
  id: number;
  name: string;
}

export interface DocumentSummary {
  id: number;
  title: string;
  doc_type: DocumentType;
  status: DocumentStatus;
  authors: string[];
  publication_year: number | null;
  venue: string | null;
  page_count: number | null;
  tags: Ref[];
  has_file: boolean;
  source_url: string | null;
  created_at: string;
  /** Search results only. Highlights are delimited by \u0002 … \u0003. */
  snippet: string | null;
  match_page: number | null;
}

/** Where a metadata value came from; "heuristic" values should be verified. */
export type MetadataSource =
  | "manual"
  | "heuristic"
  | "pdf_metadata"
  | "document_properties"
  | "front_matter"
  | "citation_meta"
  | "page_title"
  | "page_meta"
  | "filename";

export interface DocumentDetail extends DocumentSummary {
  abstract: string | null;
  keywords: string[];
  doi: string | null;
  original_filename: string | null;
  file_size: number | null;
  mime_type: string | null;
  reference_list: string[];
  note_body: string | null;
  language: string | null;
  chunk_count: number;
  collections: Ref[];
  projects: Ref[];
  metadata_sources: Partial<Record<string, MetadataSource>>;
  warnings: string[];
  error_message: string | null;
  updated_at: string;
}

export interface DocumentPage {
  items: DocumentSummary[];
  total: number;
  offset: number;
  limit: number;
}

export type SortOption = "relevance" | "added" | "title" | "year";

export interface DocumentFilters {
  q?: string;
  doc_type?: DocumentType[];
  tag?: string;
  collection_id?: number;
  project_id?: number;
  author?: string;
  year_from?: number;
  year_to?: number;
  sort?: SortOption;
  offset?: number;
  limit?: number;
}

export interface AttachmentOptions {
  collection_ids?: number[];
  project_ids?: number[];
  tags?: string[];
}

export interface DocumentUpdate {
  title?: string;
  authors?: string[];
  publication_year?: number | null;
  venue?: string | null;
  doi?: string | null;
  abstract?: string | null;
  keywords?: string[];
  note_body?: string;
}

export interface Chunk {
  id: number;
  chunk_index: number;
  page_start: number | null;
  page_end: number | null;
  section: string | null;
  text: string;
}

export interface ChunkPage {
  items: Chunk[];
  total: number;
}

export interface Collection {
  id: number;
  name: string;
  description: string | null;
  document_count: number;
  created_at: string;
}

export interface Tag {
  id: number;
  name: string;
  document_count: number;
}

export interface FacetCount {
  value: string;
  count: number;
}

export interface LibraryFacets {
  total: number;
  types: FacetCount[];
  years: FacetCount[];
  authors: FacetCount[];
  tags: Tag[];
  collections: Collection[];
}
