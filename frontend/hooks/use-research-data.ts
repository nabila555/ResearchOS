"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  analysisService,
  assistantService,
  collectionService,
  dashboardService,
  documentService,
  libraryService,
  projectService,
  systemService,
} from "@/services/researchos";
import type { AnalysisKind, DocumentFilters, ProjectInput, ProjectStatus } from "@/types/api";

export const queryKeys = {
  dashboard: ["dashboard"] as const,
  system: ["system-status"] as const,
  projects: (status?: ProjectStatus) => ["projects", status ?? "all"] as const,
};

export function useDashboard() {
  return useQuery({ queryKey: queryKeys.dashboard, queryFn: dashboardService.get });
}

export function useSystemStatus() {
  return useQuery({ queryKey: queryKeys.system, queryFn: systemService.status });
}

export function useProjects(status?: ProjectStatus) {
  return useQuery({ queryKey: queryKeys.projects(status), queryFn: () => projectService.list(status) });
}

/** Project mutations refresh both the project lists and the dashboard. */
function useInvalidateProjects() {
  const client = useQueryClient();
  return () =>
    Promise.all([
      client.invalidateQueries({ queryKey: ["projects"] }),
      client.invalidateQueries({ queryKey: queryKeys.dashboard }),
    ]);
}

export function useCreateProject() {
  const invalidate = useInvalidateProjects();
  return useMutation({ mutationFn: projectService.create, onSuccess: invalidate });
}

export function useUpdateProject() {
  const invalidate = useInvalidateProjects();
  return useMutation({
    mutationFn: ({ id, input }: { id: number; input: Partial<ProjectInput> }) =>
      projectService.update(id, input),
    onSuccess: invalidate,
  });
}

export function useDeleteProject() {
  const invalidate = useInvalidateProjects();
  return useMutation({ mutationFn: projectService.remove, onSuccess: invalidate });
}

// --- Research library ---------------------------------------------------------

export const libraryKeys = {
  documents: (filters: DocumentFilters) => ["documents", filters] as const,
  document: (id: number) => ["document", id] as const,
  chunks: (id: number, params: object) => ["document", id, "chunks", params] as const,
  facets: ["library-facets"] as const,
  collections: ["collections"] as const,
};

/** Anything that changes the library refreshes lists, facets, and the dashboard. */
export function useInvalidateLibrary() {
  const client = useQueryClient();
  return () =>
    Promise.all([
      client.invalidateQueries({ queryKey: ["documents"] }),
      client.invalidateQueries({ queryKey: ["document"] }),
      client.invalidateQueries({ queryKey: libraryKeys.facets }),
      client.invalidateQueries({ queryKey: libraryKeys.collections }),
      client.invalidateQueries({ queryKey: queryKeys.dashboard }),
      client.invalidateQueries({ queryKey: ["projects"] }),
    ]);
}

export function useDocuments(filters: DocumentFilters) {
  return useQuery({
    queryKey: libraryKeys.documents(filters),
    queryFn: () => documentService.list(filters),
    placeholderData: keepPreviousData,
  });
}

export function useDocument(id: number) {
  return useQuery({ queryKey: libraryKeys.document(id), queryFn: () => documentService.get(id) });
}

export function useDocumentChunks(id: number, params: { offset: number; limit: number; page?: number }) {
  return useQuery({
    queryKey: libraryKeys.chunks(id, params),
    queryFn: () => documentService.chunks(id, params),
    placeholderData: keepPreviousData,
  });
}

export function useLibraryFacets() {
  return useQuery({ queryKey: libraryKeys.facets, queryFn: libraryService.facets });
}

export function useCollections() {
  return useQuery({ queryKey: libraryKeys.collections, queryFn: collectionService.list });
}

export function useLibraryMutation<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const invalidate = useInvalidateLibrary();
  return useMutation({ mutationFn: fn, onSuccess: invalidate });
}

// --- AI assistant ---------------------------------------------------------------

export const assistantKeys = {
  status: ["assistant-status"] as const,
  sessions: ["chat-sessions"] as const,
  session: (id: number) => ["chat-session", id] as const,
};

/** Polls while documents are being indexed so progress is visible. */
export function useAssistantStatus() {
  return useQuery({
    queryKey: assistantKeys.status,
    queryFn: assistantService.status,
    refetchInterval: (query) => ((query.state.data?.index.pending ?? 0) > 0 ? 3000 : false),
  });
}

export function useChatSessions() {
  return useQuery({ queryKey: assistantKeys.sessions, queryFn: assistantService.sessions });
}

export function useChatSession(id: number | null) {
  return useQuery({
    queryKey: assistantKeys.session(id ?? 0),
    queryFn: () => assistantService.session(id as number),
    enabled: id !== null,
  });
}

// --- Research intelligence --------------------------------------------------------

export const analysisKeys = {
  list: (params: object) => ["analyses", params] as const,
  one: (id: number) => ["analysis", id] as const,
  profile: (documentId: number) => ["paper-profile", documentId] as const,
};

const ACTIVE = new Set(["pending", "running"]);

/** Polls every 2 s while the analysis is queued or running. */
export function useAnalysis(id: number | null) {
  return useQuery({
    queryKey: analysisKeys.one(id ?? 0),
    queryFn: () => analysisService.get(id as number),
    enabled: id !== null,
    refetchInterval: (query) => (query.state.data && ACTIVE.has(query.state.data.status) ? 2000 : false),
  });
}

export function useAnalyses(params: { kind?: AnalysisKind; document_id?: number }) {
  return useQuery({
    queryKey: analysisKeys.list(params),
    queryFn: () => analysisService.list(params),
    refetchInterval: (query) => (query.state.data?.some((a) => ACTIVE.has(a.status)) ? 3000 : false),
  });
}

export function usePaperProfile(documentId: number) {
  return useQuery({
    queryKey: analysisKeys.profile(documentId),
    queryFn: () => analysisService.profile(documentId),
    retry: false,
  });
}
