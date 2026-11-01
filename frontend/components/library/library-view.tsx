"use client";

import {
  ChevronLeft,
  ChevronRight,
  FileUp,
  Filter,
  FolderOpen,
  Library,
  Pencil,
  Plus,
  Search,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { PageContainer, PageHeader } from "@/components/layout/page-header";
import { CollectionDialog } from "@/components/library/collection-dialog";
import { ImportDialog, type ImportTab } from "@/components/library/import-dialog";
import {
  DOC_TYPE_LABELS,
  DocTypeIcon,
  HighlightedSnippet,
  formatAuthors,
} from "@/components/library/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/form-controls";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { useDocuments, useLibraryFacets, useProjects } from "@/hooks/use-research-data";
import { cn, formatRelativeTime, pluralize } from "@/lib/utils";
import type {
  Collection,
  DocumentFilters,
  DocumentSummary,
  DocumentType,
  SortOption,
} from "@/types/api";

const PAGE_SIZE = 25;

function parseIntParam(value: string | null): number | undefined {
  if (!value) return undefined;
  const n = Number.parseInt(value, 10);
  return Number.isFinite(n) ? n : undefined;
}

/** Library filters live in the URL so views are shareable and survive reloads. */
function useLibraryParams() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const filters = useMemo<DocumentFilters & { page: number }>(() => {
    const page = Math.max(1, parseIntParam(params.get("page")) ?? 1);
    return {
      q: params.get("q") ?? undefined,
      doc_type: params.getAll("type") as DocumentType[],
      tag: params.get("tag") ?? undefined,
      collection_id: parseIntParam(params.get("collection")),
      project_id: parseIntParam(params.get("project")),
      author: params.get("author") ?? undefined,
      year_from: parseIntParam(params.get("from")),
      year_to: parseIntParam(params.get("to")),
      sort: (params.get("sort") as SortOption | null) ?? undefined,
      page,
      offset: (page - 1) * PAGE_SIZE,
      limit: PAGE_SIZE,
    };
  }, [params]);

  function update(changes: Record<string, string | string[] | number | undefined | null>) {
    const next = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(changes)) {
      next.delete(key);
      if (Array.isArray(value)) value.forEach((v) => next.append(key, v));
      else if (value !== undefined && value !== null && value !== "") next.set(key, String(value));
    }
    if (!("page" in changes)) next.delete("page");
    const query = next.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }

  return { filters, update, rawParams: params };
}

export function LibraryView() {
  const { filters, update, rawParams } = useLibraryParams();
  const documents = useDocuments(filters);
  const facets = useLibraryFacets();
  const projects = useProjects();

  const [searchDraft, setSearchDraft] = useState(filters.q ?? "");
  const debouncedSearch = useDebouncedValue(searchDraft, 250);
  useEffect(() => {
    if ((debouncedSearch.trim() || undefined) !== filters.q) update({ q: debouncedSearch.trim() });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only react to the debounced text
  }, [debouncedSearch]);

  // Keep the search box in step when the query changes from outside (e.g. quick search).
  const [syncedQuery, setSyncedQuery] = useState(filters.q);
  if (filters.q !== syncedQuery) {
    setSyncedQuery(filters.q);
    if ((filters.q ?? "") !== searchDraft.trim()) setSearchDraft(filters.q ?? "");
  }

  // Deep link from the dashboard: /library?import=upload|url|note opens the import dialog.
  const importParam = rawParams.get("import");
  const [importState, setImportState] = useState<{ open: boolean; tab: ImportTab; files?: File[] }>(
    () =>
      importParam === "upload" || importParam === "url" || importParam === "note"
        ? { open: true, tab: importParam }
        : { open: false, tab: "upload" },
  );
  useEffect(() => {
    if (importParam) update({ import: undefined });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- strip the one-shot param once
  }, [importParam]);
  const [pageDrag, setPageDrag] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  const activeCollection = facets.data?.collections.find((c) => c.id === filters.collection_id);
  const activeProject = projects.data?.find((p) => p.id === filters.project_id);
  const searching = Boolean(filters.q);
  const hasFilters = Boolean(
    filters.doc_type?.length ||
      filters.tag ||
      filters.collection_id ||
      filters.project_id ||
      filters.author ||
      filters.year_from ||
      filters.year_to,
  );

  return (
    <div
      className="relative"
      onDragEnter={(e) => {
        if (e.dataTransfer.types.includes("Files")) setPageDrag(true);
      }}
    >
      {pageDrag ? (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center bg-accent/10 backdrop-blur-[1px]"
          onDragOver={(e) => e.preventDefault()}
          onDragLeave={() => setPageDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setPageDrag(false);
            const files = Array.from(e.dataTransfer.files);
            if (files.length) setImportState({ open: true, tab: "upload", files });
          }}
        >
          <div className="pointer-events-none rounded-xl border-2 border-dashed border-accent bg-surface px-10 py-8 text-center shadow-xl">
            <FileUp className="mx-auto size-6 text-accent" />
            <p className="mt-2 text-sm font-medium">Drop files to import</p>
          </div>
        </div>
      ) : null}

      <PageContainer>
        <PageHeader
          title={activeCollection?.name ?? (activeProject ? `Project: ${activeProject.name}` : "Research Library")}
          description={
            activeCollection
              ? activeCollection.description || `${pluralize(activeCollection.document_count, "item")} in this collection`
              : facets.data
                ? `${pluralize(facets.data.total, "item")} in your library`
                : "Your papers, articles, and notes"
          }
          actions={
            <Button variant="primary" onClick={() => setImportState({ open: true, tab: "upload" })}>
              <Plus /> Add
            </Button>
          }
        />

        <div className="grid gap-6 lg:grid-cols-[13rem_1fr]">
          <aside className={cn("space-y-5 lg:block", showFilters ? "block" : "hidden")}>
            {/* Re-mount when text filters change elsewhere (e.g. a chip is cleared) so drafts reset. */}
            <FilterPanel
              key={`${filters.author ?? ""}|${filters.year_from ?? ""}|${filters.year_to ?? ""}`}
              filters={filters}
              update={update}
            />
          </aside>

          <section className="min-w-0 space-y-3">
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-subtle-foreground" />
                <Input
                  value={searchDraft}
                  onChange={(e) => setSearchDraft(e.target.value)}
                  placeholder="Search titles, authors, abstracts, and full text…"
                  className="pl-8"
                  aria-label="Search library"
                />
              </div>
              <Select
                aria-label="Sort"
                value={filters.sort ?? (searching ? "relevance" : "added")}
                onChange={(e) => update({ sort: e.target.value })}
                className="w-auto"
              >
                {searching ? <option value="relevance">Relevance</option> : null}
                <option value="added">Recently added</option>
                <option value="title">Title</option>
                <option value="year">Year</option>
              </Select>
              <Button className="lg:hidden" onClick={() => setShowFilters((v) => !v)} aria-expanded={showFilters}>
                <Filter /> <span className="sr-only sm:not-sr-only">Filters</span>
              </Button>
            </div>

            {hasFilters ? (
              <ActiveFilters filters={filters} update={update} collection={activeCollection} projectName={activeProject?.name} />
            ) : null}

            {documents.isError ? (
              <ErrorState error={documents.error} onRetry={() => documents.refetch()} />
            ) : documents.isPending ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }, (_, i) => (
                  <Skeleton key={i} className="h-20" />
                ))}
              </div>
            ) : documents.data.total === 0 ? (
              searching || hasFilters ? (
                <EmptyState
                  icon={Search}
                  title="No matching items"
                  description="Try different words or remove some filters."
                  className="py-12"
                />
              ) : (
                <EmptyState
                  icon={Library}
                  title={activeCollection ? "This collection is empty" : "Your library is empty"}
                  description="Upload PDFs, Word documents, Markdown, or text files, import a web article, or write a note. You can also drag files onto this page."
                  action={
                    <Button size="sm" variant="primary" onClick={() => setImportState({ open: true, tab: "upload" })}>
                      <FileUp /> Import files
                    </Button>
                  }
                  className="py-14"
                />
              )
            ) : (
              <>
                <Card className={cn("divide-y divide-border", documents.isFetching && "opacity-70 transition-opacity")}>
                  {documents.data.items.map((doc) => (
                    <DocumentRow key={doc.id} doc={doc} onTag={(tag) => update({ tag })} />
                  ))}
                </Card>
                <Pagination
                  total={documents.data.total}
                  page={filters.page}
                  onPage={(page) => update({ page: page === 1 ? undefined : page })}
                />
              </>
            )}
          </section>
        </div>
      </PageContainer>

      <ImportDialog
        open={importState.open}
        onOpenChange={(open) => setImportState((s) => ({ ...s, open, files: open ? s.files : undefined }))}
        initialTab={importState.tab}
        initialFiles={importState.files}
        defaultCollectionId={filters.collection_id}
      />
    </div>
  );
}

function DocumentRow({ doc, onTag }: { doc: DocumentSummary; onTag: (tag: string) => void }) {
  const meta = [formatAuthors(doc.authors), doc.publication_year, doc.venue].filter(Boolean).join(" · ");
  return (
    <article className="group flex gap-3 px-4 py-3 hover:bg-surface-muted/50">
      <DocTypeIcon type={doc.doc_type} className="mt-0.5" />
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <Link
            href={`/library/${doc.id}`}
            className="text-sm leading-snug font-medium hover:text-accent focus-visible:underline focus-visible:outline-none"
          >
            {doc.title}
          </Link>
          <span className="hidden shrink-0 text-xs text-subtle-foreground sm:inline">
            {formatRelativeTime(doc.created_at)}
          </span>
        </div>
        {meta ? <p className="mt-0.5 truncate text-[13px] text-muted-foreground">{meta}</p> : null}
        {doc.snippet ? (
          <p className="mt-1.5 line-clamp-2 text-[13px] leading-relaxed text-foreground/80">
            {doc.match_page ? (
              <span className="mr-1.5 font-mono text-[11px] text-subtle-foreground">p.{doc.match_page}</span>
            ) : null}
            <HighlightedSnippet text={doc.snippet} />
          </p>
        ) : null}
        <div className="mt-1.5 flex flex-wrap items-center gap-1">
          <Badge>{DOC_TYPE_LABELS[doc.doc_type]}</Badge>
          {doc.page_count ? <Badge>{pluralize(doc.page_count, "page")}</Badge> : null}
          {doc.tags.map((tag) => (
            <button key={tag.id} type="button" onClick={() => onTag(tag.name)} title={`Filter by ${tag.name}`}>
              <Badge tone="accent">#{tag.name}</Badge>
            </button>
          ))}
        </div>
      </div>
    </article>
  );
}

function Pagination({ total, page, onPage }: { total: number; page: number; onPage: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const start = (page - 1) * PAGE_SIZE + 1;
  const end = Math.min(total, page * PAGE_SIZE);
  return (
    <div className="flex items-center justify-between text-[13px] text-muted-foreground">
      <span>
        {start}–{end} of {total.toLocaleString("en")}
      </span>
      {pages > 1 ? (
        <div className="flex gap-1">
          <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page">
            <ChevronLeft />
          </Button>
          <span className="flex items-center px-1 tabular-nums">
            {page} / {pages}
          </span>
          <Button size="sm" variant="ghost" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page">
            <ChevronRight />
          </Button>
        </div>
      ) : null}
    </div>
  );
}

type Update = ReturnType<typeof useLibraryParams>["update"];

function ActiveFilters({
  filters,
  update,
  collection,
  projectName,
}: {
  filters: DocumentFilters;
  update: Update;
  collection?: Collection;
  projectName?: string;
}) {
  const chips: { label: string; clear: () => void }[] = [];
  if (collection) chips.push({ label: `Collection: ${collection.name}`, clear: () => update({ collection: undefined }) });
  if (filters.project_id)
    chips.push({ label: `Project: ${projectName ?? filters.project_id}`, clear: () => update({ project: undefined }) });
  for (const type of filters.doc_type ?? [])
    chips.push({
      label: DOC_TYPE_LABELS[type],
      clear: () => update({ type: (filters.doc_type ?? []).filter((t) => t !== type) }),
    });
  if (filters.tag) chips.push({ label: `#${filters.tag}`, clear: () => update({ tag: undefined }) });
  if (filters.author) chips.push({ label: `Author: ${filters.author}`, clear: () => update({ author: undefined }) });
  if (filters.year_from || filters.year_to)
    chips.push({
      label: `Year: ${filters.year_from ?? "…"}–${filters.year_to ?? "…"}`,
      clear: () => update({ from: undefined, to: undefined }),
    });

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {chips.map((chip) => (
        <span
          key={chip.label}
          className="inline-flex items-center gap-1 rounded-md border border-border bg-surface py-0.5 pr-0.5 pl-2 text-xs"
        >
          {chip.label}
          <button type="button" onClick={chip.clear} className="rounded p-0.5 hover:bg-surface-muted" aria-label={`Remove filter ${chip.label}`}>
            <X className="size-3" />
          </button>
        </span>
      ))}
      <button
        type="button"
        className="text-xs text-muted-foreground hover:text-foreground"
        onClick={() =>
          update({ collection: undefined, project: undefined, type: undefined, tag: undefined, author: undefined, from: undefined, to: undefined })
        }
      >
        Clear all
      </button>
    </div>
  );
}

function FilterSection({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <h3 className="text-[11px] font-semibold tracking-wide text-subtle-foreground uppercase">{title}</h3>
        {action}
      </div>
      {children}
    </div>
  );
}

function FilterButton({
  active,
  onClick,
  children,
  count,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  count?: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-[13px] transition-colors",
        active ? "bg-accent-soft text-accent-soft-foreground" : "text-muted-foreground hover:bg-surface-muted hover:text-foreground",
      )}
    >
      <span className="min-w-0 flex-1 truncate">{children}</span>
      {count !== undefined ? <span className="text-xs tabular-nums opacity-70">{count}</span> : null}
    </button>
  );
}

function FilterPanel({ filters, update }: { filters: DocumentFilters; update: Update }) {
  const facets = useLibraryFacets();
  const [collectionDialog, setCollectionDialog] = useState<{ open: boolean; collection?: Collection }>({ open: false });
  const [authorDraft, setAuthorDraft] = useState(filters.author ?? "");
  const [yearFrom, setYearFrom] = useState(filters.year_from?.toString() ?? "");
  const [yearTo, setYearTo] = useState(filters.year_to?.toString() ?? "");

  if (facets.isPending) return <Skeleton className="h-64" />;
  if (facets.isError) return null;
  const data = facets.data;
  const selectedTypes = filters.doc_type ?? [];

  return (
    <>
      <FilterSection
        title="Collections"
        action={
          <button
            type="button"
            className="rounded p-0.5 text-subtle-foreground hover:bg-surface-muted hover:text-foreground"
            onClick={() => setCollectionDialog({ open: true })}
            aria-label="New collection"
          >
            <Plus className="size-3.5" />
          </button>
        }
      >
        <div className="space-y-0.5">
          <FilterButton active={!filters.collection_id} onClick={() => update({ collection: undefined })} count={data.total}>
            All items
          </FilterButton>
          {data.collections.map((c) => (
            <div key={c.id} className="group relative">
              <FilterButton active={filters.collection_id === c.id} onClick={() => update({ collection: c.id })} count={c.document_count}>
                <FolderOpen className="mr-1.5 inline size-3.5 align-[-2px]" />
                {c.name}
              </FilterButton>
              <button
                type="button"
                className="absolute top-1/2 right-7 hidden -translate-y-1/2 rounded p-0.5 text-subtle-foreground group-hover:block hover:text-foreground"
                onClick={() => setCollectionDialog({ open: true, collection: c })}
                aria-label={`Edit collection ${c.name}`}
              >
                <Pencil className="size-3" />
              </button>
            </div>
          ))}
          {data.collections.length === 0 ? (
            <p className="px-2 text-xs text-subtle-foreground">No collections yet.</p>
          ) : null}
        </div>
      </FilterSection>

      {data.types.length ? (
        <FilterSection title="Type">
          <div className="space-y-0.5">
            {data.types.map((t) => {
              const type = t.value as DocumentType;
              const active = selectedTypes.includes(type);
              return (
                <FilterButton
                  key={type}
                  active={active}
                  count={t.count}
                  onClick={() =>
                    update({ type: active ? selectedTypes.filter((x) => x !== type) : [...selectedTypes, type] })
                  }
                >
                  {DOC_TYPE_LABELS[type]}
                </FilterButton>
              );
            })}
          </div>
        </FilterSection>
      ) : null}

      <FilterSection title="Year">
        <form
          className="flex items-center gap-1.5"
          onSubmit={(e) => {
            e.preventDefault();
            update({ from: yearFrom || undefined, to: yearTo || undefined });
          }}
          onBlur={() => update({ from: yearFrom || undefined, to: yearTo || undefined })}
        >
          <Input
            aria-label="From year"
            inputMode="numeric"
            placeholder={data.years.at(-1)?.value ?? "From"}
            value={yearFrom}
            onChange={(e) => setYearFrom(e.target.value.replace(/\D/g, "").slice(0, 4))}
            className="h-7 text-[13px]"
          />
          <span className="text-subtle-foreground">–</span>
          <Input
            aria-label="To year"
            inputMode="numeric"
            placeholder={data.years[0]?.value ?? "To"}
            value={yearTo}
            onChange={(e) => setYearTo(e.target.value.replace(/\D/g, "").slice(0, 4))}
            className="h-7 text-[13px]"
          />
          <button type="submit" className="sr-only">
            Apply
          </button>
        </form>
      </FilterSection>

      <FilterSection title="Author">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            update({ author: authorDraft.trim() || undefined });
          }}
        >
          <Input
            list="author-facets"
            aria-label="Filter by author"
            placeholder="Name…"
            value={authorDraft}
            onChange={(e) => setAuthorDraft(e.target.value)}
            onBlur={() => update({ author: authorDraft.trim() || undefined })}
            className="h-7 text-[13px]"
          />
          <datalist id="author-facets">
            {data.authors.map((a) => (
              <option key={a.value} value={a.value} />
            ))}
          </datalist>
        </form>
      </FilterSection>

      {data.tags.length ? (
        <FilterSection title="Tags">
          <div className="flex flex-wrap gap-1">
            {data.tags.map((tag) => {
              const active = filters.tag?.toLowerCase() === tag.name.toLowerCase();
              return (
                <button key={tag.id} type="button" aria-pressed={active} onClick={() => update({ tag: active ? undefined : tag.name })}>
                  <Badge tone={active ? "accent" : "neutral"} className="hover:text-foreground">
                    #{tag.name} <span className="opacity-60">{tag.document_count}</span>
                  </Badge>
                </button>
              );
            })}
          </div>
        </FilterSection>
      ) : null}

      <CollectionDialog
        open={collectionDialog.open}
        collection={collectionDialog.collection}
        onOpenChange={(open) => setCollectionDialog((s) => ({ ...s, open }))}
        onDeleted={() => {
          if (filters.collection_id === collectionDialog.collection?.id) update({ collection: undefined });
        }}
      />
    </>
  );
}
