"use client";

import { CheckCircle2, CircleAlert, Copy, FileUp, Link2, Loader2, NotebookPen, X } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { ACCEPTED_EXTENSIONS, formatBytes } from "@/components/library/shared";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input, Label, Select, Textarea } from "@/components/ui/form-controls";
import { TagInput } from "@/components/ui/tag-input";
import {
  useCollections,
  useInvalidateLibrary,
  useLibraryFacets,
  useProjects,
} from "@/hooks/use-research-data";
import { ApiError } from "@/lib/api";
import { cn, pluralize } from "@/lib/utils";
import { documentService } from "@/services/researchos";
import type { AttachmentOptions } from "@/types/api";

export type ImportTab = "upload" | "url" | "note";

const TABS: { value: ImportTab; label: string; icon: typeof FileUp }[] = [
  { value: "upload", label: "Upload files", icon: FileUp },
  { value: "url", label: "From URL", icon: Link2 },
  { value: "note", label: "Note", icon: NotebookPen },
];

interface ImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialTab?: ImportTab;
  initialFiles?: File[];
  /** Pre-select a collection (e.g. the one currently open in the library). */
  defaultCollectionId?: number;
}

export function ImportDialog({
  open,
  onOpenChange,
  initialTab = "upload",
  initialFiles,
  defaultCollectionId,
}: ImportDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title="Add to library"
        description="Files are validated and stored on this computer only."
        className="max-w-xl"
      >
        {open ? (
          <ImportForm
            initialTab={initialTab}
            initialFiles={initialFiles}
            defaultCollectionId={defaultCollectionId}
            onClose={() => onOpenChange(false)}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

type UploadState =
  | { status: "queued" }
  | { status: "uploading"; progress: number }
  | { status: "processing" }
  | { status: "done"; documentId: number }
  | { status: "duplicate"; documentId: number; message: string }
  | { status: "error"; message: string };

interface QueueItem {
  key: string;
  file: File;
  state: UploadState;
}

function fileKey(file: File) {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

function ImportForm({
  initialTab,
  initialFiles,
  defaultCollectionId,
  onClose,
}: {
  initialTab: ImportTab;
  initialFiles?: File[];
  defaultCollectionId?: number;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<ImportTab>(initialTab);
  const [collectionId, setCollectionId] = useState<number | "">(defaultCollectionId ?? "");
  const [projectId, setProjectId] = useState<number | "">("");
  const [tags, setTags] = useState<string[]>([]);
  const collections = useCollections();
  const projects = useProjects();
  const facets = useLibraryFacets();
  const invalidate = useInvalidateLibrary();

  const options: AttachmentOptions = {
    collection_ids: collectionId === "" ? [] : [collectionId],
    project_ids: projectId === "" ? [] : [projectId],
    tags,
  };

  return (
    <div className="space-y-4">
      <div role="tablist" className="flex gap-1 rounded-md bg-surface-muted p-0.5">
        {TABS.map(({ value, label, icon: Icon }) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={cn(
              "flex h-7 flex-1 items-center justify-center gap-1.5 rounded text-[13px] transition-colors",
              tab === value
                ? "bg-surface font-medium text-foreground shadow-xs"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon className="size-3.5" />
            {label}
          </button>
        ))}
      </div>

      {tab === "upload" ? (
        <UploadTab initialFiles={initialFiles} options={options} onUploaded={invalidate} onClose={onClose} />
      ) : tab === "url" ? (
        <UrlTab options={options} onDone={invalidate} onClose={onClose} />
      ) : (
        <NoteTab options={options} onDone={invalidate} onClose={onClose} />
      )}

      <details className="rounded-md border border-border px-3 py-2 text-[13px]">
        <summary className="cursor-pointer text-muted-foreground select-none">
          Organise while importing (optional)
        </summary>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor="import-collection">Collection</Label>
            <Select
              id="import-collection"
              value={collectionId}
              onChange={(e) => setCollectionId(e.target.value ? Number(e.target.value) : "")}
            >
              <option value="">None</option>
              {collections.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="import-project">Project</Label>
            <Select
              id="import-project"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value ? Number(e.target.value) : "")}
            >
              <option value="">None</option>
              {projects.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="import-tags">Tags</Label>
            <TagInput
              id="import-tags"
              value={tags}
              onChange={setTags}
              suggestions={facets.data?.tags.map((t) => t.name)}
            />
          </div>
        </div>
      </details>
    </div>
  );
}

function UploadTab({
  initialFiles,
  options,
  onUploaded,
  onClose,
}: {
  initialFiles?: File[];
  options: AttachmentOptions;
  onUploaded: () => void;
  onClose: () => void;
}) {
  const [queue, setQueue] = useState<QueueItem[]>(() =>
    (initialFiles ?? []).map((file) => ({ key: fileKey(file), file, state: { status: "queued" } })),
  );
  const [running, setRunning] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function addFiles(files: FileList | File[]) {
    setQueue((current) => {
      const keys = new Set(current.map((i) => i.key));
      const added = Array.from(files)
        .filter((f) => !keys.has(fileKey(f)))
        .map((file) => ({ key: fileKey(file), file, state: { status: "queued" } as UploadState }));
      return [...current, ...added];
    });
  }

  function update(key: string, state: UploadState) {
    setQueue((current) => current.map((i) => (i.key === key ? { ...i, state } : i)));
  }

  async function start() {
    setRunning(true);
    let succeeded = 0;
    for (const item of queue.filter((i) => i.state.status === "queued" || i.state.status === "error")) {
      update(item.key, { status: "uploading", progress: 0 });
      try {
        const doc = await documentService.upload(item.file, options, (fraction) =>
          update(item.key, fraction >= 1 ? { status: "processing" } : { status: "uploading", progress: fraction }),
        );
        update(item.key, { status: "done", documentId: doc.id });
        succeeded += 1;
      } catch (error) {
        const apiError = error instanceof ApiError ? error : null;
        const existing = apiError?.body?.existing_document_id;
        if (apiError?.status === 409 && typeof existing === "number") {
          update(item.key, { status: "duplicate", documentId: existing, message: apiError.message });
        } else {
          update(item.key, {
            status: "error",
            message: error instanceof Error ? error.message : "Upload failed",
          });
        }
      }
    }
    setRunning(false);
    if (succeeded) {
      onUploaded();
      toast.success(`Imported ${succeeded} ${succeeded === 1 ? "file" : "files"}`);
    }
  }

  const pending = queue.filter((i) => i.state.status === "queued" || i.state.status === "error").length;
  const allFinished = queue.length > 0 && pending === 0 && !running;

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          addFiles(e.dataTransfer.files);
        }}
        className={cn(
          "flex flex-col items-center justify-center rounded-lg border border-dashed px-4 py-6 text-center transition-colors",
          dragging ? "border-accent bg-accent-soft/40" : "border-border-strong",
        )}
      >
        <FileUp className="size-5 text-subtle-foreground" aria-hidden />
        <p className="mt-2 text-sm">
          Drop files here or{" "}
          <button
            type="button"
            className="font-medium text-accent hover:underline"
            onClick={() => inputRef.current?.click()}
          >
            browse
          </button>
        </p>
        <p className="mt-1 text-xs text-subtle-foreground">PDF, Word (.docx), Markdown, or plain text</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED_EXTENSIONS.join(",")}
          className="sr-only"
          onChange={(e) => {
            if (e.target.files) addFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </div>

      {queue.length ? (
        <ul className="max-h-60 divide-y divide-border overflow-y-auto rounded-md border border-border">
          {queue.map((item) => (
            <li key={item.key} className="flex items-center gap-3 px-3 py-2">
              <QueueStatusIcon state={item.state} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px]">{item.file.name}</p>
                <QueueStatusText state={item.state} size={item.file.size} onNavigate={onClose} />
              </div>
              {item.state.status === "queued" && !running ? (
                <button
                  type="button"
                  className="rounded p-1 text-subtle-foreground hover:bg-surface-muted hover:text-foreground"
                  aria-label={`Remove ${item.file.name}`}
                  onClick={() => setQueue((q) => q.filter((i) => i.key !== item.key))}
                >
                  <X className="size-3.5" />
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose} disabled={running}>
          {allFinished ? "Close" : "Cancel"}
        </Button>
        <Button variant="primary" onClick={start} disabled={running || pending === 0}>
          {running ? (
            <>
              <Loader2 className="animate-spin" /> Importing…
            </>
          ) : (
            pending ? `Import ${pluralize(pending, "file")}` : "Import"
          )}
        </Button>
      </div>
    </div>
  );
}

function QueueStatusIcon({ state }: { state: UploadState }) {
  switch (state.status) {
    case "uploading":
    case "processing":
      return <Loader2 className="size-4 shrink-0 animate-spin text-accent" aria-hidden />;
    case "done":
      return <CheckCircle2 className="size-4 shrink-0 text-success" aria-hidden />;
    case "duplicate":
      return <Copy className="size-4 shrink-0 text-warning" aria-hidden />;
    case "error":
      return <CircleAlert className="size-4 shrink-0 text-danger" aria-hidden />;
    default:
      return <FileUp className="size-4 shrink-0 text-subtle-foreground" aria-hidden />;
  }
}

function QueueStatusText({
  state,
  size,
  onNavigate,
}: {
  state: UploadState;
  size: number;
  onNavigate: () => void;
}) {
  const base = "text-xs";
  switch (state.status) {
    case "queued":
      return <p className={cn(base, "text-subtle-foreground")}>{formatBytes(size)} · ready</p>;
    case "uploading":
      return (
        <div className="mt-1 h-1 overflow-hidden rounded-full bg-surface-muted">
          <div className="h-full bg-accent transition-[width]" style={{ width: `${Math.round(state.progress * 100)}%` }} />
        </div>
      );
    case "processing":
      return <p className={cn(base, "text-muted-foreground")}>Extracting text and metadata…</p>;
    case "done":
      return (
        <Link href={`/library/${state.documentId}`} onClick={onNavigate} className={cn(base, "text-accent hover:underline")}>
          Imported · open
        </Link>
      );
    case "duplicate":
      return (
        <p className={cn(base, "text-muted-foreground")}>
          Already in library ·{" "}
          <Link href={`/library/${state.documentId}`} onClick={onNavigate} className="text-accent hover:underline">
            open existing
          </Link>
        </p>
      );
    case "error":
      return <p className={cn(base, "text-danger")}>{state.message}</p>;
  }
}

function UrlTab({
  options,
  onDone,
  onClose,
}: {
  options: AttachmentOptions;
  onDone: () => void;
  onClose: () => void;
}) {
  const [url, setUrl] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<{ message: string; existingId?: number } | null>(null);
  const [createdId, setCreatedId] = useState<number | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const doc = await documentService.importUrl(url.trim(), options);
      setCreatedId(doc.id);
      onDone();
      toast.success(`Imported “${doc.title}”`);
    } catch (e) {
      const apiError = e instanceof ApiError ? e : null;
      const existing = apiError?.body?.existing_document_id;
      setError({
        message: e instanceof Error ? e.message : "Import failed",
        existingId: typeof existing === "number" ? existing : undefined,
      });
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div>
        <Label htmlFor="import-url">Web article or PDF link</Label>
        <Input
          id="import-url"
          type="url"
          required
          placeholder="https://arxiv.org/pdf/…"
          value={url}
          onChange={(e) => {
            setUrl(e.target.value);
            setCreatedId(null);
          }}
          autoFocus
        />
        <p className="mt-1.5 text-xs text-subtle-foreground">
          The page is downloaded once by your local backend; scholarly metadata tags are used when present.
        </p>
      </div>
      {error ? (
        <p role="alert" className="text-[13px] text-danger">
          {error.message}{" "}
          {error.existingId ? (
            <Link href={`/library/${error.existingId}`} onClick={onClose} className="text-accent hover:underline">
              Open existing
            </Link>
          ) : null}
        </p>
      ) : null}
      {createdId ? (
        <p className="text-[13px] text-success">
          Imported.{" "}
          <Link href={`/library/${createdId}`} onClick={onClose} className="text-accent hover:underline">
            Open document
          </Link>
        </p>
      ) : null}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onClose}>
          Close
        </Button>
        <Button type="submit" variant="primary" disabled={pending || !url.trim()}>
          {pending ? (
            <>
              <Loader2 className="animate-spin" /> Fetching…
            </>
          ) : (
            "Import URL"
          )}
        </Button>
      </div>
    </form>
  );
}

function NoteTab({
  options,
  onDone,
  onClose,
}: {
  options: AttachmentOptions;
  onDone: () => void;
  onClose: () => void;
}) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await documentService.createNote(title.trim(), body, options);
      onDone();
      toast.success("Note saved");
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save note");
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div>
        <Label htmlFor="note-title">Title</Label>
        <Input id="note-title" required maxLength={500} value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />
      </div>
      <div>
        <Label htmlFor="note-body">Note (Markdown supported)</Label>
        <Textarea id="note-body" rows={8} value={body} onChange={(e) => setBody(e.target.value)} className="font-mono text-[13px]" />
      </div>
      {error ? (
        <p role="alert" className="text-[13px] text-danger">
          {error}
        </p>
      ) : null}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" disabled={pending || !title.trim()}>
          {pending ? "Saving…" : "Save note"}
        </Button>
      </div>
    </form>
  );
}
