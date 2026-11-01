"use client";

import {
  AlertTriangle,
  ArrowLeft,
  ExternalLink,
  FileSearch,
  Info,
  Pencil,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { DetectiveCard, PaperProfileCard } from "@/components/analysis/document-intelligence";
import { PageContainer } from "@/components/layout/page-header";
import { MetadataDialog } from "@/components/library/metadata-dialog";
import { DOC_TYPE_LABELS, DocTypeIcon, formatBytes, formatPages } from "@/components/library/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/form-controls";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { TagInput } from "@/components/ui/tag-input";
import {
  useCollections,
  useDocument,
  useDocumentChunks,
  useLibraryFacets,
  useLibraryMutation,
  useProjects,
} from "@/hooks/use-research-data";
import { ApiError } from "@/lib/api";
import { formatRelativeTime, pluralize } from "@/lib/utils";
import { assistantService, documentService } from "@/services/researchos";
import type { DocumentDetail, Ref } from "@/types/api";

const FIELD_LABELS: Record<string, string> = {
  title: "title",
  authors: "authors",
  publication_year: "year",
  abstract: "abstract",
  keywords: "keywords",
  doi: "DOI",
  reference_list: "references",
};

export function DocumentDetailView({ id }: { id: number }) {
  const doc = useDocument(id);

  return (
    <PageContainer>
      <Link
        href="/library"
        className="mb-4 inline-flex items-center gap-1 text-[13px] text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" /> Library
      </Link>
      {doc.isError ? (
        doc.error instanceof ApiError && doc.error.status === 404 ? (
          <EmptyState icon={FileSearch} title="Document not found" description="It may have been removed from the library." />
        ) : (
          <ErrorState error={doc.error} onRetry={() => doc.refetch()} />
        )
      ) : doc.isPending ? (
        <div className="space-y-4">
          <Skeleton className="h-24" />
          <Skeleton className="h-64" />
        </div>
      ) : (
        <DocumentDetailContent doc={doc.data} />
      )}
    </PageContainer>
  );
}

function DocumentDetailContent({ doc }: { doc: DocumentDetail }) {
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const autoDetected = Object.entries(doc.metadata_sources)
    .filter(([field, source]) => (source === "heuristic" || source === "filename") && FIELD_LABELS[field])
    .map(([field]) => FIELD_LABELS[field]);

  return (
    <div className="space-y-6">
      <header>
        <div className="flex flex-wrap items-center gap-2 text-[13px] text-muted-foreground">
          <DocTypeIcon type={doc.doc_type} />
          <span>{DOC_TYPE_LABELS[doc.doc_type]}</span>
          {doc.page_count ? <span>· {pluralize(doc.page_count, "page")}</span> : null}
          <span>· added {formatRelativeTime(doc.created_at)}</span>
        </div>
        <h1 className="mt-2 text-xl leading-snug font-semibold tracking-tight sm:text-2xl">{doc.title}</h1>
        {doc.authors.length ? (
          <p className="mt-1.5 text-sm text-foreground/85">{doc.authors.join(", ")}</p>
        ) : (
          <p className="mt-1.5 text-sm text-subtle-foreground italic">Authors unknown</p>
        )}
        <p className="mt-1 text-[13px] text-muted-foreground">
          {[doc.venue, doc.publication_year ?? "Year unknown"].filter(Boolean).join(" · ")}
          {doc.doi ? (
            <>
              {" · "}
              <a
                href={`https://doi.org/${doc.doi}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent hover:underline"
              >
                doi:{doc.doi}
              </a>
            </>
          ) : null}
        </p>

        <div className="mt-4 flex flex-wrap gap-2">
          {doc.has_file ? (
            <Button asChild variant="primary">
              <a href={documentService.fileUrl(doc.id)} target="_blank" rel="noopener noreferrer">
                <ExternalLink /> Open {DOC_TYPE_LABELS[doc.doc_type]}
              </a>
            </Button>
          ) : null}
          {doc.source_url ? (
            <Button asChild>
              <a href={doc.source_url} target="_blank" rel="noopener noreferrer">
                <ExternalLink /> Source
              </a>
            </Button>
          ) : null}
          <Button onClick={() => setEditing(true)}>
            <Pencil /> Edit details
          </Button>
          <Button variant="ghost" className="hover:text-danger" onClick={() => setDeleting(true)}>
            <Trash2 /> Remove
          </Button>
        </div>
      </header>

      {doc.warnings.map((warning) => (
        <div key={warning} role="alert" className="flex gap-2 rounded-md border border-warning/40 bg-warning-soft/60 p-3 text-[13px]">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
          {warning}
        </div>
      ))}
      {autoDetected.length ? (
        <div className="flex gap-2 rounded-md border border-border bg-surface-muted/60 p-3 text-[13px] text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0" />
          <p>
            Detected automatically from the document text: {autoDetected.join(", ")}. Please check them;{" "}
            <button type="button" className="text-accent hover:underline" onClick={() => setEditing(true)}>
              edit details
            </button>{" "}
            to correct anything.
          </p>
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[1fr_18rem]">
        <div className="min-w-0 space-y-6">
          {doc.doc_type === "note" ? <NoteEditor doc={doc} /> : null}
          {doc.abstract ? (
            <Card>
              <CardHeader title="Abstract" />
              <CardBody>
                <p className="text-sm leading-relaxed whitespace-pre-line">{doc.abstract}</p>
              </CardBody>
            </Card>
          ) : null}
          {doc.keywords.length ? (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[13px] text-muted-foreground">Keywords:</span>
              {doc.keywords.map((k) => (
                <Badge key={k}>{k}</Badge>
              ))}
            </div>
          ) : null}
          {doc.chunk_count > 0 ? <PaperProfileCard documentId={doc.id} /> : null}
          {doc.chunk_count > 0 && doc.doc_type !== "note" ? <DetectiveCard documentId={doc.id} /> : null}
          {doc.doc_type !== "note" ? <ExtractedText doc={doc} /> : null}
          {doc.reference_list.length ? <References references={doc.reference_list} /> : null}
        </div>

        <aside className="space-y-4">
          <OrganiseCard doc={doc} />
          <Card>
            <CardHeader title="Details" />
            <CardBody>
              <dl className="space-y-2 text-[13px]">
                {doc.original_filename ? <DetailRow label="File">{doc.original_filename}</DetailRow> : null}
                {doc.file_size !== null ? <DetailRow label="Size">{formatBytes(doc.file_size)}</DetailRow> : null}
                <DetailRow label="Indexed passages">{doc.chunk_count}</DetailRow>
                <DetailRow label="AI search">
                  <AiIndexStatus doc={doc} />
                </DetailRow>
                <DetailRow label="Updated">{formatRelativeTime(doc.updated_at)}</DetailRow>
              </dl>
            </CardBody>
          </Card>
        </aside>
      </div>

      <MetadataDialog doc={doc} open={editing} onOpenChange={setEditing} />
      <DeleteDocumentDialog doc={doc} open={deleting} onOpenChange={setDeleting} />
    </div>
  );
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 truncate text-right">{children}</dd>
    </div>
  );
}

function OrganiseCard({ doc }: { doc: DocumentDetail }) {
  const facets = useLibraryFacets();
  const collections = useCollections();
  const projects = useProjects();
  const setTags = useLibraryMutation((names: string[]) => documentService.setTags(doc.id, names));
  const setCollections = useLibraryMutation((ids: number[]) => documentService.setCollections(doc.id, ids));
  const setProjects = useLibraryMutation((ids: number[]) => documentService.setProjects(doc.id, ids));

  const onError = (error: unknown) => toast.error(error instanceof Error ? error.message : "Could not save");

  return (
    <Card>
      <CardHeader title="Organise" />
      <CardBody className="space-y-4">
        <div>
          <p className="mb-1.5 text-[13px] font-medium">Tags</p>
          <TagInput
            value={doc.tags.map((t) => t.name)}
            onChange={(names) => setTags.mutate(names, { onError })}
            suggestions={facets.data?.tags.map((t) => t.name)}
            disabled={setTags.isPending}
          />
        </div>
        <Checklist
          title="Collections"
          empty="No collections yet. Create one from the library sidebar."
          options={collections.data?.map((c) => ({ id: c.id, name: c.name })) ?? []}
          selected={doc.collections}
          disabled={setCollections.isPending}
          onChange={(ids) => setCollections.mutate(ids, { onError })}
        />
        <Checklist
          title="Projects"
          empty="No projects yet."
          options={projects.data?.map((p) => ({ id: p.id, name: p.name })) ?? []}
          selected={doc.projects}
          disabled={setProjects.isPending}
          onChange={(ids) => setProjects.mutate(ids, { onError })}
        />
      </CardBody>
    </Card>
  );
}

function Checklist({
  title,
  empty,
  options,
  selected,
  disabled,
  onChange,
}: {
  title: string;
  empty: string;
  options: Ref[];
  selected: Ref[];
  disabled: boolean;
  onChange: (ids: number[]) => void;
}) {
  const selectedIds = new Set(selected.map((s) => s.id));
  return (
    <fieldset disabled={disabled}>
      <legend className="mb-1.5 text-[13px] font-medium">{title}</legend>
      {options.length === 0 ? (
        <p className="text-xs text-subtle-foreground">{empty}</p>
      ) : (
        <div className="max-h-40 space-y-1 overflow-y-auto">
          {options.map((option) => (
            <label key={option.id} className="flex cursor-pointer items-center gap-2 text-[13px]">
              <input
                type="checkbox"
                className="size-3.5 accent-[var(--accent)]"
                checked={selectedIds.has(option.id)}
                onChange={(e) => {
                  const next = new Set(selectedIds);
                  if (e.target.checked) next.add(option.id);
                  else next.delete(option.id);
                  onChange([...next]);
                }}
              />
              <span className="truncate">{option.name}</span>
            </label>
          ))}
        </div>
      )}
    </fieldset>
  );
}

const CHUNKS_PER_PAGE = 20;

function ExtractedText({ doc }: { doc: DocumentDetail }) {
  const [offset, setOffset] = useState(0);
  // Citations link here with ?page=N to open the passage's page directly.
  const initialPage = Number(useSearchParams().get("page")) || undefined;
  const [pageDraft, setPageDraft] = useState(initialPage ? String(initialPage) : "");
  const [page, setPage] = useState<number | undefined>(initialPage);
  const chunks = useDocumentChunks(doc.id, { offset, limit: CHUNKS_PER_PAGE, page });

  return (
    <Card>
      <CardHeader
        title="Extracted text"
        description={`${pluralize(doc.chunk_count, "passage")} indexed for search${doc.page_count ? ", with page numbers" : ""}.`}
        action={
          doc.page_count ? (
            <form
              className="flex items-center gap-1.5"
              onSubmit={(e) => {
                e.preventDefault();
                const n = Number(pageDraft);
                setOffset(0);
                setPage(Number.isInteger(n) && n >= 1 ? n : undefined);
              }}
            >
              <Input
                aria-label="Go to page"
                placeholder="Page"
                inputMode="numeric"
                value={pageDraft}
                onChange={(e) => setPageDraft(e.target.value.replace(/\D/g, ""))}
                className="h-7 w-16 text-[13px]"
              />
              {page ? (
                <Button
                  size="sm"
                  variant="ghost"
                  type="button"
                  onClick={() => {
                    setPage(undefined);
                    setPageDraft("");
                  }}
                >
                  All
                </Button>
              ) : null}
            </form>
          ) : null
        }
      />
      <CardBody>
        {chunks.isError ? (
          <ErrorState error={chunks.error} onRetry={() => chunks.refetch()} />
        ) : chunks.isPending ? (
          <Skeleton className="h-40" />
        ) : chunks.data.total === 0 ? (
          <p className="text-[13px] text-muted-foreground">
            {page ? `No text found on page ${page}.` : "No text was extracted from this document."}
          </p>
        ) : (
          <>
            <ol className="space-y-4">
              {chunks.data.items.map((chunk) => (
                <li key={chunk.id} className="border-l-2 border-border pl-3">
                  <p className="mb-1 font-mono text-[11px] text-subtle-foreground">
                    {[formatPages(chunk.page_start, chunk.page_end), chunk.section].filter(Boolean).join(" · ") ||
                      `Passage ${chunk.chunk_index + 1}`}
                  </p>
                  <p className="text-[13px] leading-relaxed text-foreground/90">{chunk.text}</p>
                </li>
              ))}
            </ol>
            {chunks.data.total > CHUNKS_PER_PAGE ? (
              <div className="mt-4 flex items-center justify-between text-[13px] text-muted-foreground">
                <span>
                  {offset + 1}–{Math.min(offset + CHUNKS_PER_PAGE, chunks.data.total)} of {chunks.data.total}
                </span>
                <div className="flex gap-1">
                  <Button size="sm" variant="ghost" disabled={offset === 0} onClick={() => setOffset(offset - CHUNKS_PER_PAGE)}>
                    Previous
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={offset + CHUNKS_PER_PAGE >= chunks.data.total}
                    onClick={() => setOffset(offset + CHUNKS_PER_PAGE)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            ) : null}
          </>
        )}
      </CardBody>
    </Card>
  );
}

function References({ references }: { references: string[] }) {
  const [expanded, setExpanded] = useState(false);
  const shown = expanded ? references : references.slice(0, 8);
  return (
    <Card>
      <CardHeader
        title={`References (${references.length})`}
        description="As found in the document text. Not verified against external databases."
      />
      <CardBody>
        <ol className="space-y-1.5 text-[13px] leading-relaxed text-foreground/85">
          {shown.map((ref, i) => (
            <li key={i}>{ref}</li>
          ))}
        </ol>
        {references.length > 8 ? (
          <button type="button" className="mt-3 text-[13px] text-accent hover:underline" onClick={() => setExpanded(!expanded)}>
            {expanded ? "Show fewer" : `Show all ${references.length}`}
          </button>
        ) : null}
      </CardBody>
    </Card>
  );
}

function NoteEditor({ doc }: { doc: DocumentDetail }) {
  const [body, setBody] = useState(doc.note_body ?? "");
  const save = useLibraryMutation((note_body: string) => documentService.update(doc.id, { note_body }));
  const dirty = body !== (doc.note_body ?? "");

  return (
    <Card>
      <CardHeader
        title="Note"
        action={
          <Button
            size="sm"
            variant="primary"
            disabled={!dirty || save.isPending}
            onClick={() =>
              save.mutate(body, {
                onSuccess: () => toast.success("Note saved"),
                onError: (e) => toast.error(e.message),
              })
            }
          >
            {save.isPending ? "Saving…" : dirty ? "Save" : "Saved"}
          </Button>
        }
      />
      <CardBody>
        <Textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={14}
          className="font-mono text-[13px]"
          aria-label="Note body"
        />
      </CardBody>
    </Card>
  );
}

function DeleteDocumentDialog({
  doc,
  open,
  onOpenChange,
}: {
  doc: DocumentDetail;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const remove = useLibraryMutation((id: number) => documentService.remove(id));

  async function confirm() {
    try {
      await remove.mutateAsync(doc.id);
      toast.success(`Removed “${doc.title}”`);
      router.push("/library");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not remove document");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title="Remove from library?"
        description={
          doc.has_file
            ? "The stored file, its extracted text, and its search index entries are deleted from this computer."
            : "The item and its search index entries are deleted."
        }
      >
        <p className="text-sm">
          <span className="font-medium">{doc.title}</span> will be permanently removed.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <DialogClose asChild>
            <Button variant="ghost">Cancel</Button>
          </DialogClose>
          <Button variant="danger" onClick={confirm} disabled={remove.isPending}>
            {remove.isPending ? "Removing…" : "Remove"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

const INDEX_LABELS = {
  ready: { tone: "success", label: "Indexed" },
  pending: { tone: "accent", label: "Indexing…" },
  failed: { tone: "danger", label: "Failed" },
  none: { tone: "neutral", label: "Not indexed" },
} as const;

function AiIndexStatus({ doc }: { doc: DocumentDetail }) {
  const reindex = useLibraryMutation((id: number) => assistantService.reindex([id]));
  const info = INDEX_LABELS[doc.ai_index_status] ?? INDEX_LABELS.none;
  return (
    <span className="inline-flex items-center gap-1.5" title={doc.ai_index_error ?? undefined}>
      <Badge tone={info.tone}>{info.label}</Badge>
      {doc.ai_index_status === "failed" || doc.ai_index_status === "none" ? (
        <button
          type="button"
          className="text-xs text-accent hover:underline disabled:opacity-50"
          disabled={reindex.isPending}
          onClick={() => reindex.mutate(doc.id, { onError: (e) => toast.error(e.message) })}
        >
          Retry
        </button>
      ) : null}
    </span>
  );
}
