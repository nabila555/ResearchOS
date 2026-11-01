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
  ai_index_status: IndexStatus;
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
  volume: string | null;
  issue: string | null;
  pages: string | null;
  publisher: string | null;
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
  ai_index_error: string | null;
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
  volume?: string | null;
  issue?: string | null;
  pages?: string | null;
  publisher?: string | null;
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

// --- AI assistant ---------------------------------------------------------------

export type IndexStatus = "none" | "pending" | "ready" | "failed";

export interface ChatScope {
  collection_id?: number;
  project_id?: number;
  document_ids?: number[];
}

export interface SourcePassage {
  n: number;
  chunk_id: number;
  document_id: number;
  title: string;
  authors: string[];
  year: number | null;
  page_start: number | null;
  page_end: number | null;
  section: string | null;
  text: string;
  score: number;
  semantic_similarity: number | null;
}

export type ChatMessageStatus = "complete" | "error" | "refused" | "insufficient_evidence";

export interface ChatMessage {
  id: number;
  session_id: number;
  role: "user" | "assistant";
  content: string;
  provider: string | null;
  model: string | null;
  status: ChatMessageStatus | null;
  grounded: boolean;
  sources: SourcePassage[];
  cited: number[];
  invalid_citations: number[];
  notes: string[];
  created_at: string;
}

export interface ChatSession {
  id: number;
  title: string;
  scope: ChatScope;
  message_count: number;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatSessionDetail extends ChatSession {
  messages: ChatMessage[];
}

export type AskEvent =
  | { type: "user_message"; message: ChatMessage }
  | { type: "sources"; sources: SourcePassage[]; semantic: boolean; notes: string[] }
  | { type: "delta"; text: string }
  | { type: "done"; message: ChatMessage }
  | { type: "error"; message: string; chat_message?: ChatMessage };

export interface ProviderInfo {
  name: string;
  label: string;
  model: string;
  cloud: boolean;
}

export interface AssistantStatus {
  chat_provider: string;
  providers: ProviderInfo[];
  cloud_consent: boolean;
  embed_model: string;
  index: {
    documents_total: number;
    ready: number;
    pending: number;
    failed: number;
    not_indexed: number;
    chunks_total: number;
    chunks_embedded: number;
    waiting_for_provider: boolean;
  };
}

// --- Research intelligence --------------------------------------------------------

export type AnalysisKind = "profile" | "comparison" | "gap_analysis" | "detective";
export type AnalysisStatus = "pending" | "running" | "done" | "failed" | "cancelled";

export interface Evidence {
  chunk_id: number | null;
  page_start: number | null;
  page_end: number | null;
  section: string | null;
  quote: string;
  verified: boolean;
  reason: string | null;
}

export interface ProfileStatement {
  text: string;
  evidence: Evidence;
}

export type FieldStatus = "verified" | "partial" | "unverified" | "not_reported";

export interface ProfileFieldValue {
  status: FieldStatus;
  statements: ProfileStatement[];
}

export interface PaperProfile {
  document_id: number;
  provider: string;
  model: string;
  stale: boolean;
  passages_used: number;
  fields: (ProfileFieldValue & { key: string; label: string })[];
  updated_at: string;
}

export interface ComparisonResult {
  documents: { id: number; title: string; year: number | null; authors: string[] }[];
  fields: { key: string; label: string }[];
  profiles: Record<string, Record<string, ProfileFieldValue>>;
}

export interface GapItem {
  statement: string;
  basis: "literature" | "hypothesis";
  rationale: string;
  papers: { label: string; document_id: number; title: string }[];
  notes: string[];
}

export interface GapResult {
  focus: string | null;
  papers: { label: string; document_id: number; title: string; year: number | null }[];
  categories: { key: string; label: string; items: GapItem[] }[];
}

export interface DetectiveObservation {
  category: string;
  severity: "low" | "medium" | "high";
  observation: string;
  kind: "quoted" | "absence";
  evidence: Evidence | null;
}

export interface DetectiveResult {
  document: { id: number; title: string };
  observations: DetectiveObservation[];
  checklist: {
    key: string;
    label: string;
    status: "reported" | "not_found" | "unclear" | "unverified";
    evidence: Evidence | null;
  }[];
  excerpts_analyzed: number;
  excerpt_pages?: number[];
}

export interface Analysis {
  id: number;
  kind: AnalysisKind;
  status: AnalysisStatus;
  title: string;
  document_ids: number[];
  params: { focus?: string; label?: string };
  progress: number;
  progress_message: string | null;
  error: string | null;
  provider: string;
  model: string;
  report_id: number | null;
  created_at: string;
  updated_at: string;
  result?: unknown;
}

export interface AnalysisCreate {
  kind: AnalysisKind;
  document_ids?: number[];
  collection_id?: number;
  project_id?: number;
  focus?: string;
}

// --- Knowledge management ---------------------------------------------------------

export type CitationStyle = "apa" | "mla" | "chicago" | "ieee";

export interface FormattedCitation {
  document_id: number;
  number: number | null;
  text: string;
  markdown: string;
  parts: { text: string; italic: boolean }[];
  missing: string[];
  kind: "article" | "web" | "document";
}

export type GraphNodeType =
  | "paper"
  | "author"
  | "topic"
  | "keyword"
  | "collection"
  | "method"
  | "finding"
  | "question";

export interface GraphNode {
  id: string;
  type: GraphNodeType;
  label: string;
  data: {
    degree: number;
    document_id?: number;
    year?: number | null;
    page?: number | null;
    quote?: string;
    papers?: number;
  };
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  weight: number;
  label: string | null;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: Partial<Record<GraphNodeType, number>>;
  has_profile?: boolean;
}

export interface ClaimRef {
  text: string;
  supported: boolean;
  papers: { label: string; document_id: number }[];
  notes: string[];
}

export interface ThemeSummaryResult {
  theme: string;
  papers: { label: string; document_id: number; title: string }[];
  synthesis: ClaimRef[];
  agreements: ClaimRef[];
  disagreements: ClaimRef[];
}

export interface ReviewTheme {
  id: number;
  name: string;
  description: string | null;
  position: number;
  items: { document_id: number; note: string | null; title: string; authors: string[]; year: number | null }[];
  summary: {
    analysis_id: number;
    status: AnalysisStatus;
    progress: number;
    progress_message: string | null;
    error: string | null;
    model: string;
    result: ThemeSummaryResult | null;
    stale: boolean;
    updated_at: string;
  } | null;
}

export interface LiteratureReview {
  id: number;
  title: string;
  research_question: string | null;
  introduction: string | null;
  project_id: number | null;
  citation_style: CitationStyle;
  themes: ReviewTheme[];
  created_at: string;
  updated_at: string;
}

export interface ReviewSummary {
  id: number;
  title: string;
  research_question: string | null;
  theme_count: number;
  updated_at: string;
}
