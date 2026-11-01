"use client";

import { FolderKanban, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { PageContainer, PageHeader } from "@/components/layout/page-header";
import { PROJECT_STATUSES, ProjectFormDialog } from "@/components/projects/project-form-dialog";
import { ProjectStatusBadge } from "@/components/projects/project-status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { useDeleteProject, useProjects } from "@/hooks/use-research-data";
import { cn, formatRelativeTime, pluralize } from "@/lib/utils";
import type { Project, ProjectStatus } from "@/types/api";

type Filter = ProjectStatus | "all";
const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  ...PROJECT_STATUSES,
];

export function ProjectsView() {
  const [filter, setFilter] = useState<Filter>("all");
  const projects = useProjects(filter === "all" ? undefined : filter);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Project | undefined>();
  const [deleting, setDeleting] = useState<Project | undefined>();

  function openCreate() {
    setEditing(undefined);
    setFormOpen(true);
  }

  function openEdit(project: Project) {
    setEditing(project);
    setFormOpen(true);
  }

  return (
    <PageContainer>
      <PageHeader
        title="Research Projects"
        description="Frame research questions and track their progress."
        actions={
          <Button variant="primary" onClick={openCreate}>
            <Plus /> New project
          </Button>
        }
      />

      <div
        role="tablist"
        aria-label="Filter projects by status"
        className="mb-4 flex gap-1 overflow-x-auto"
      >
        {FILTERS.map((f) => (
          <button
            key={f.value}
            role="tab"
            aria-selected={filter === f.value}
            onClick={() => setFilter(f.value)}
            className={cn(
              "h-7 rounded-md px-2.5 text-[13px] transition-colors",
              filter === f.value
                ? "bg-surface-muted font-medium text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {projects.isError ? (
        <ErrorState error={projects.error} onRetry={() => projects.refetch()} />
      ) : projects.isPending ? (
        <div className="grid gap-3 md:grid-cols-2">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      ) : projects.data.length === 0 ? (
        <EmptyState
          icon={FolderKanban}
          title={filter === "all" ? "No projects yet" : `No ${filter} projects`}
          description={
            filter === "all"
              ? "A project frames a research question and collects the sources, notes, and reports that answer it."
              : "Try a different filter."
          }
          action={
            filter === "all" ? (
              <Button size="sm" onClick={openCreate}>
                <Plus /> New project
              </Button>
            ) : undefined
          }
          className="py-14"
        />
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {projects.data.map((project) => (
            <li key={project.id}>
              <ProjectCard
                project={project}
                onEdit={() => openEdit(project)}
                onDelete={() => setDeleting(project)}
              />
            </li>
          ))}
        </ul>
      )}

      <ProjectFormDialog open={formOpen} onOpenChange={setFormOpen} project={editing} />
      <DeleteProjectDialog project={deleting} onClose={() => setDeleting(undefined)} />
    </PageContainer>
  );
}

function ProjectCard({
  project,
  onEdit,
  onDelete,
}: {
  project: Project;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <Card className="group flex h-full flex-col p-4">
      <div className="flex items-start justify-between gap-3">
        <h3 className="min-w-0 text-sm font-semibold leading-snug">{project.name}</h3>
        <ProjectStatusBadge status={project.status} />
      </div>
      {project.research_question ? (
        <p className="mt-1.5 line-clamp-2 text-[13px] text-foreground/85">
          {project.research_question}
        </p>
      ) : null}
      {project.description ? (
        <p className="mt-1 line-clamp-2 text-[13px] text-muted-foreground">
          {project.description}
        </p>
      ) : null}
      <div className="mt-auto flex items-center justify-between gap-2 pt-4">
        <p className="text-xs text-subtle-foreground">
          {pluralize(project.document_count, "source")} · updated{" "}
          {formatRelativeTime(project.updated_at)}
        </p>
        <div className="flex gap-0.5">
          <Button size="icon" variant="ghost" onClick={onEdit} aria-label={`Edit ${project.name}`}>
            <Pencil />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            onClick={onDelete}
            aria-label={`Delete ${project.name}`}
            className="hover:text-danger"
          >
            <Trash2 />
          </Button>
        </div>
      </div>
    </Card>
  );
}

function DeleteProjectDialog({ project, onClose }: { project?: Project; onClose: () => void }) {
  const remove = useDeleteProject();

  async function confirm() {
    if (!project) return;
    try {
      await remove.mutateAsync(project.id);
      toast.success(`Deleted “${project.name}”`);
      onClose();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not delete project");
    }
  }

  return (
    <Dialog open={project !== undefined} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title="Delete project?"
        description="The project is removed. Documents and reports in your library are kept."
      >
        <p className="text-sm">
          <span className="font-medium">{project?.name}</span> will be permanently deleted.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <DialogClose asChild>
            <Button variant="ghost">Cancel</Button>
          </DialogClose>
          <Button variant="danger" onClick={confirm} disabled={remove.isPending}>
            {remove.isPending ? "Deleting…" : "Delete project"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
