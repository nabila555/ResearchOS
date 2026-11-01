"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  collectionService,
  dashboardService,
  documentService,
  libraryService,
  projectService,
  systemService,
} from "@/services/researchos";
import type { DocumentFilters, ProjectInput, ProjectStatus } from "@/types/api";

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
