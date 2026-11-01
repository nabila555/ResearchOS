"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Input, Label, Select, Textarea } from "@/components/ui/form-controls";
import { useCreateProject, useUpdateProject } from "@/hooks/use-research-data";
import type { Project, ProjectStatus } from "@/types/api";

export const PROJECT_STATUSES: { value: ProjectStatus; label: string }[] = [
  { value: "active", label: "Active" },
  { value: "paused", label: "Paused" },
  { value: "completed", label: "Completed" },
  { value: "archived", label: "Archived" },
];

interface ProjectFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** When provided the dialog edits this project; otherwise it creates one. */
  project?: Project;
}

export function ProjectFormDialog({ open, onOpenChange, project }: ProjectFormDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={project ? "Edit project" : "New research project"}
        description="Projects group sources, notes, and reports around a research question."
      >
        {/* Re-mount the form each time the dialog opens so fields reset. */}
        {open ? <ProjectForm project={project} onDone={() => onOpenChange(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}

function ProjectForm({ project, onDone }: { project?: Project; onDone: () => void }) {
  const [name, setName] = useState(project?.name ?? "");
  const [question, setQuestion] = useState(project?.research_question ?? "");
  const [description, setDescription] = useState(project?.description ?? "");
  const [status, setStatus] = useState<ProjectStatus>(project?.status ?? "active");
  const create = useCreateProject();
  const update = useUpdateProject();
  const pending = create.isPending || update.isPending;
  const error = create.error ?? update.error;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const input = {
      name: name.trim(),
      research_question: question.trim() || null,
      description: description.trim() || null,
      status,
    };
    try {
      if (project) {
        await update.mutateAsync({ id: project.id, input });
        toast.success("Project updated");
      } else {
        await create.mutateAsync(input);
        toast.success("Project created");
      }
      onDone();
    } catch {
      // The error is rendered inline below.
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <Label htmlFor="project-name">Name</Label>
        <Input
          id="project-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Sleep and memory consolidation"
          maxLength={200}
          required
          autoFocus
        />
      </div>
      <div>
        <Label htmlFor="project-question">Research question</Label>
        <Textarea
          id="project-question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="What are you trying to find out?"
          maxLength={2000}
          rows={2}
        />
      </div>
      <div>
        <Label htmlFor="project-description">Description</Label>
        <Textarea
          id="project-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Scope, context, or notes (optional)"
          maxLength={5000}
          rows={3}
        />
      </div>
      {project ? (
        <div>
          <Label htmlFor="project-status">Status</Label>
          <Select
            id="project-status"
            value={status}
            onChange={(e) => setStatus(e.target.value as ProjectStatus)}
          >
            {PROJECT_STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </Select>
        </div>
      ) : null}

      {error ? (
        <p role="alert" className="text-[13px] text-danger">
          {error.message}
        </p>
      ) : null}

      <div className="flex justify-end gap-2 pt-1">
        <DialogClose asChild>
          <Button type="button" variant="ghost">
            Cancel
          </Button>
        </DialogClose>
        <Button type="submit" variant="primary" disabled={pending || !name.trim()}>
          {pending ? "Saving…" : project ? "Save changes" : "Create project"}
        </Button>
      </div>
    </form>
  );
}
