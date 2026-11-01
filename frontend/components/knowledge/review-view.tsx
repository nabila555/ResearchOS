"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  BookOpen,
  Download,
  Layers,
  Loader2,
  Plus,
  ScrollText,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { DocumentPicker } from "@/components/analysis/document-picker";
import { AnalysisDisclaimer } from "@/components/analysis/shared";
import { PageContainer, PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Input, Label, Select, Textarea } from "@/components/ui/form-controls";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { formatAuthors } from "@/components/library/shared";
import { cn, formatRelativeTime, pluralize } from "@/lib/utils";
import { reportService, reviewService } from "@/services/researchos";
import type { CitationStyle, ClaimRef, LiteratureReview, ReviewTheme } from "@/types/api";

const reviewKey = (id: number) => ["review", id] as const;

function useReviewMutation(reviewId: number) {
  const queryClient = useQueryClient();
  return async (action: () => Promise<LiteratureReview | void>, success?: string) => {
    try {
      const next = await action();
      if (next) queryClient.setQueryData(reviewKey(reviewId), next);
      else await queryClient.invalidateQueries({ queryKey: reviewKey(reviewId) });
      await queryClient.invalidateQueries({ queryKey: ["reviews"] });
      if (success) toast.success(success);
      return true;
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Something went wrong");
      return false;
    }
  };
}

export function ReviewView() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const selectedId = params.get("id") ? Number(params.get("id")) : null;
  const select = (id: number | null) => router.replace(id ? `${pathname}?id=${id}` : pathname, { scroll: false });
  const reviews = useQuery({ queryKey: ["reviews"], queryFn: reviewService.list });
  const [creating, setCreating] = useState(false);

  return (
    <PageContainer>
      <PageHeader
        title="Literature Review"
        description="Organise sources into themes, draft cited syntheses, and export the review to Markdown."
        actions={
          <Button variant="primary" onClick={() => setCreating(true)}>
            <Plus /> New review
          </Button>
        }
      />
      <div className="grid gap-6 lg:grid-cols-[15rem_1fr]">
        <aside>
          {reviews.isPending ? (
            <Skeleton className="h-24" />
          ) : reviews.data?.length ? (
            <ul className="space-y-0.5">
              {reviews.data.map((r) => (
                <li key={r.id}>
                  <button
                    type="button"
                    onClick={() => select(r.id)}
                    className={cn("w-full rounded-md px-2.5 py-2 text-left", r.id === selectedId ? "bg-surface-muted" : "hover:bg-surface-muted/60")}
                  >
                    <span className="block truncate text-[13px] font-medium">{r.title}</span>
                    <span className="text-[11px] text-subtle-foreground">
                      {pluralize(r.theme_count, "theme")} · {formatRelativeTime(r.updated_at)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-2 text-xs text-subtle-foreground">No reviews yet.</p>
          )}
        </aside>
        <section className="min-w-0">
          {selectedId === null ? (
            <EmptyState
              icon={BookOpen}
              title="No review open"
              description="Create a review, group your sources into themes, and generate cited thematic summaries."
              action={
                <Button size="sm" variant="primary" onClick={() => setCreating(true)}>
                  <Plus /> New review
                </Button>
              }
              className="py-16"
            />
          ) : (
            <ReviewEditor key={selectedId} reviewId={selectedId} onDeleted={() => select(null)} />
          )}
        </section>
      </div>
      <NewReviewDialog open={creating} onOpenChange={setCreating} onCreated={(id) => select(id)} />
    </PageContainer>
  );
}

function NewReviewDialog({ open, onOpenChange, onCreated }: { open: boolean; onOpenChange: (o: boolean) => void; onCreated: (id: number) => void }) {
  const [title, setTitle] = useState("");
  const [question, setQuestion] = useState("");
  const queryClient = useQueryClient();

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    try {
      const review = await reviewService.create({ title: title.trim(), research_question: question.trim() || null });
      await queryClient.invalidateQueries({ queryKey: ["reviews"] });
      onOpenChange(false);
      setTitle("");
      setQuestion("");
      onCreated(review.id);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not create review");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="New literature review">
        <form onSubmit={submit} className="space-y-4">
          <div>
            <Label htmlFor="review-title">Title</Label>
            <Input id="review-title" value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={300} autoFocus />
          </div>
          <div>
            <Label htmlFor="review-question">Research question (optional)</Label>
            <Textarea id="review-question" value={question} onChange={(e) => setQuestion(e.target.value)} rows={2} maxLength={2000} />
          </div>
          <div className="flex justify-end gap-2">
            <DialogClose asChild>
              <Button type="button" variant="ghost">
                Cancel
              </Button>
            </DialogClose>
            <Button type="submit" variant="primary" disabled={!title.trim()}>
              Create
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ReviewEditor({ reviewId, onDeleted }: { reviewId: number; onDeleted: () => void }) {
  const router = useRouter();
  const review = useQuery({
    queryKey: reviewKey(reviewId),
    queryFn: () => reviewService.get(reviewId),
    refetchInterval: (query) =>
      query.state.data?.themes.some((t) => t.summary && (t.summary.status === "pending" || t.summary.status === "running")) ? 2500 : false,
  });
  const mutate = useReviewMutation(reviewId);
  const [newTheme, setNewTheme] = useState("");
  const [suggesting, setSuggesting] = useState(false);

  if (review.isError) return <ErrorState error={review.error} onRetry={() => review.refetch()} />;
  if (review.isPending) return <Skeleton className="h-96" />;
  const data = review.data;

  return (
    <div className="space-y-5">
      <Card>
        <CardBody className="space-y-3 pt-4">
          <Input
            aria-label="Review title"
            defaultValue={data.title}
            onBlur={(e) => e.target.value.trim() && e.target.value !== data.title && mutate(() => reviewService.update(reviewId, { title: e.target.value.trim() }))}
            className="h-9 border-transparent px-1 text-lg font-semibold shadow-none hover:border-border"
          />
          <Textarea
            aria-label="Research question"
            placeholder="Research question"
            defaultValue={data.research_question ?? ""}
            onBlur={(e) => e.target.value !== (data.research_question ?? "") && mutate(() => reviewService.update(reviewId, { research_question: e.target.value || null }))}
            rows={2}
            className="min-h-0 border-transparent px-1 shadow-none hover:border-border"
          />
          <div className="flex flex-wrap items-center gap-2">
            <Select
              aria-label="Citation style"
              value={data.citation_style}
              onChange={(e) => mutate(() => reviewService.update(reviewId, { citation_style: e.target.value as CitationStyle }))}
              className="h-7 w-auto text-xs"
            >
              <option value="apa">APA 7th</option>
              <option value="mla">MLA 9th</option>
              <option value="chicago">Chicago</option>
              <option value="ieee">IEEE</option>
            </Select>
            <Button asChild size="sm">
              <a href={reviewService.exportUrl(reviewId)} download>
                <Download /> Export Markdown
              </a>
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={async () => {
                try {
                  const { report_id } = await reportService.saveReview(reviewId);
                  toast.success("Saved to Reports (PDF export available there)", {
                    action: { label: "Open", onClick: () => router.push(`/reports?id=${report_id}`) },
                  });
                } catch (error) {
                  toast.error(error instanceof Error ? error.message : "Could not save");
                }
              }}
            >
              <ScrollText /> Save as report
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setSuggesting(true)}>
              <Layers /> Suggest themes
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="ml-auto hover:text-danger"
              onClick={async () => {
                if (window.confirm(`Delete “${data.title}”? Your library documents are kept.`)) {
                  if (await mutate(() => reviewService.remove(reviewId), "Review deleted")) onDeleted();
                }
              }}
            >
              <Trash2 /> Delete
            </Button>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Introduction" description="Your own words. Exported before the themes." />
        <CardBody>
          <Textarea
            aria-label="Introduction"
            defaultValue={data.introduction ?? ""}
            onBlur={(e) => e.target.value !== (data.introduction ?? "") && mutate(() => reviewService.update(reviewId, { introduction: e.target.value || null }))}
            rows={4}
            placeholder="Context, scope and how sources were selected…"
          />
        </CardBody>
      </Card>

      {data.themes.length ? (
        <nav aria-label="Outline" className="rounded-md border border-border bg-surface-muted/40 px-4 py-3 text-[13px]">
          <p className="mb-1 text-xs font-medium text-muted-foreground">Outline</p>
          <ol className="list-decimal space-y-0.5 pl-5">
            <li>Introduction</li>
            {data.themes.map((t) => (
              <li key={t.id}>
                <a href={`#theme-${t.id}`} className="hover:text-accent">
                  {t.name}
                </a>{" "}
                <span className="text-subtle-foreground">· {pluralize(t.items.length, "source")}{t.summary?.status === "done" ? " · synthesis" : ""}</span>
              </li>
            ))}
            <li>References</li>
          </ol>
        </nav>
      ) : null}

      {data.themes.map((theme, index) => (
        <ThemeCard key={theme.id} theme={theme} reviewId={reviewId} isFirst={index === 0} isLast={index === data.themes.length - 1} />
      ))}

      <form
        className="flex gap-2"
        onSubmit={async (e) => {
          e.preventDefault();
          if (await mutate(() => reviewService.addTheme(reviewId, { name: newTheme.trim() }))) setNewTheme("");
        }}
      >
        <Input value={newTheme} onChange={(e) => setNewTheme(e.target.value)} placeholder="New theme name, e.g. “Measurement approaches”" maxLength={200} aria-label="New theme name" />
        <Button type="submit" disabled={!newTheme.trim()}>
          <Plus /> Add theme
        </Button>
      </form>

      <SuggestDialog open={suggesting} onOpenChange={setSuggesting} reviewId={reviewId} />
    </div>
  );
}

function ThemeCard({ theme, reviewId, isFirst, isLast }: { theme: ReviewTheme; reviewId: number; isFirst: boolean; isLast: boolean }) {
  const mutate = useReviewMutation(reviewId);
  const [adding, setAdding] = useState(false);
  const items = theme.items;
  const save = (next: { document_id: number; note: string | null }[]) => mutate(() => reviewService.setItems(theme.id, next));
  const asInput = items.map((i) => ({ document_id: i.document_id, note: i.note }));
  const summary = theme.summary;
  const running = summary && (summary.status === "pending" || summary.status === "running");

  function move(from: number, to: number) {
    const next = [...asInput];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    save(next);
  }

  return (
    <Card id={`theme-${theme.id}`}>
      <div className="flex items-start gap-2 px-4 pt-4">
        <div className="min-w-0 flex-1">
          <Input
            aria-label="Theme name"
            defaultValue={theme.name}
            onBlur={(e) => e.target.value.trim() && e.target.value !== theme.name && mutate(() => reviewService.updateTheme(theme.id, { name: e.target.value.trim() }))}
            className="h-8 border-transparent px-1 font-semibold shadow-none hover:border-border"
          />
          <Input
            aria-label="Theme description"
            placeholder="Short description (optional)"
            defaultValue={theme.description ?? ""}
            onBlur={(e) => e.target.value !== (theme.description ?? "") && mutate(() => reviewService.updateTheme(theme.id, { description: e.target.value || null }))}
            className="h-7 border-transparent px-1 text-[13px] text-muted-foreground shadow-none hover:border-border"
          />
        </div>
        <div className="flex">
          <Button size="icon" variant="ghost" disabled={isFirst} onClick={() => mutate(() => reviewService.updateTheme(theme.id, { position: Math.max(0, theme.position - 1) }))} aria-label="Move theme up">
            <ArrowUp />
          </Button>
          <Button size="icon" variant="ghost" disabled={isLast} onClick={() => mutate(() => reviewService.updateTheme(theme.id, { position: theme.position + 1 }))} aria-label="Move theme down">
            <ArrowDown />
          </Button>
          <Button size="icon" variant="ghost" className="hover:text-danger" onClick={() => window.confirm(`Delete theme “${theme.name}”?`) && mutate(() => reviewService.removeTheme(theme.id))} aria-label="Delete theme">
            <Trash2 />
          </Button>
        </div>
      </div>
      <CardBody className="space-y-4 pt-2">
        {items.length === 0 ? (
          <p className="text-[13px] text-subtle-foreground">No sources yet.</p>
        ) : (
          <ul className="divide-y divide-border rounded-md border border-border">
            {items.map((item, i) => (
              <li key={item.document_id} className="flex gap-2 px-3 py-2">
                <div className="min-w-0 flex-1">
                  <Link href={`/library/${item.document_id}`} className="text-[13px] font-medium hover:text-accent">
                    {item.title}
                  </Link>
                  <p className="text-xs text-subtle-foreground">{[formatAuthors(item.authors, 2), item.year].filter(Boolean).join(" · ") || "—"}</p>
                  <Input
                    aria-label="Note"
                    placeholder="Note on how this source fits the theme…"
                    defaultValue={item.note ?? ""}
                    onBlur={(e) => {
                      if (e.target.value === (item.note ?? "")) return;
                      save(asInput.map((x) => (x.document_id === item.document_id ? { ...x, note: e.target.value || null } : x)));
                    }}
                    className="mt-1 h-7 text-xs"
                  />
                </div>
                <div className="flex flex-col">
                  <button type="button" disabled={i === 0} onClick={() => move(i, i - 1)} className="rounded p-0.5 text-subtle-foreground hover:text-foreground disabled:opacity-30" aria-label="Move up">
                    <ArrowUp className="size-3.5" />
                  </button>
                  <button type="button" disabled={i === items.length - 1} onClick={() => move(i, i + 1)} className="rounded p-0.5 text-subtle-foreground hover:text-foreground disabled:opacity-30" aria-label="Move down">
                    <ArrowDown className="size-3.5" />
                  </button>
                  <button type="button" onClick={() => save(asInput.filter((x) => x.document_id !== item.document_id))} className="rounded p-0.5 text-subtle-foreground hover:text-danger" aria-label={`Remove ${item.title}`}>
                    <X className="size-3.5" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={() => setAdding(true)}>
            <Plus /> Add sources
          </Button>
          <Button
            size="sm"
            variant={summary?.status === "done" ? "ghost" : "primary"}
            disabled={!items.length || !!running}
            onClick={() => mutate(() => reviewService.summarise(theme.id), "Synthesis queued")}
          >
            {running ? <Loader2 className="animate-spin" /> : <Sparkles />}
            {summary?.status === "done" ? "Regenerate synthesis" : "Generate synthesis"}
          </Button>
        </div>

        {summary ? <ThemeSummaryView summary={summary} /> : null}
      </CardBody>
      <AddSourcesDialog
        open={adding}
        onOpenChange={setAdding}
        initial={items.map((i) => i.document_id)}
        onSave={(ids) => save(ids.map((id) => asInput.find((x) => x.document_id === id) ?? { document_id: id, note: null }))}
      />
    </Card>
  );
}

function ThemeSummaryView({ summary }: { summary: NonNullable<ReviewTheme["summary"]> }) {
  if (summary.status === "pending" || summary.status === "running") {
    return (
      <div className="rounded-md border border-border p-3">
        <p className="flex items-center gap-2 text-[13px]">
          <Loader2 className="size-3.5 animate-spin text-accent" /> {summary.progress_message ?? "Working…"}
        </p>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-muted">
          <div className="h-full bg-accent transition-[width]" style={{ width: `${Math.max(4, summary.progress * 100)}%` }} />
        </div>
      </div>
    );
  }
  if (summary.status === "failed") {
    return <p className="rounded-md bg-danger-soft/60 px-3 py-2 text-[13px]">Synthesis failed: {summary.error}</p>;
  }
  if (summary.status !== "done" || !summary.result) return null;
  const result = summary.result;
  const label = (id: number) => result.papers.find((p) => p.document_id === id);

  const claim = (c: ClaimRef, i: number) => (
    <span key={i} className={cn(!c.supported && "rounded bg-danger-soft/60 px-0.5")} title={c.notes.join(" ") || undefined}>
      {c.text.replace(/\.$/, "")}
      {c.papers.map((p) => (
        <Link key={p.label} href={`/library/${p.document_id}`} title={label(p.document_id)?.title} className="ml-0.5 align-[1px] font-mono text-[10px] text-accent hover:underline">
          [{p.label}]
        </Link>
      ))}
      {!c.supported ? <AlertTriangle className="ml-0.5 inline size-3 text-danger" /> : null}.{" "}
    </span>
  );

  return (
    <div className="space-y-3 rounded-md border border-border p-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-subtle-foreground">
        <Badge tone="accent">AI synthesis</Badge>
        <span>
          {summary.model} · {formatRelativeTime(summary.updated_at)}
        </span>
        {summary.stale ? <Badge tone="warning">Sources changed since</Badge> : null}
      </div>
      <p className="text-sm leading-relaxed">{result.synthesis.map(claim)}</p>
      {(["agreements", "disagreements"] as const).map((key) =>
        result[key].length ? (
          <div key={key}>
            <p className="mb-1 text-xs font-medium text-muted-foreground">{key === "agreements" ? "Points of agreement" : "Points of disagreement"}</p>
            <ul className="list-disc space-y-0.5 pl-5 text-[13px]">
              {result[key].map((c, i) => (
                <li key={i}>{claim(c, i)}</li>
              ))}
            </ul>
          </div>
        ) : null,
      )}
      <p className="text-xs text-subtle-foreground">
        {result.papers.map((p) => `${p.label} = ${p.title}`).join(" · ")}
      </p>
      <AnalysisDisclaimer>
        Each sentence lists the papers it is based on (from their verified profiles). Highlighted sentences have no valid
        source and are marked “unsupported” in the export.
      </AnalysisDisclaimer>
    </div>
  );
}

function AddSourcesDialog({ open, onOpenChange, initial, onSave }: { open: boolean; onOpenChange: (o: boolean) => void; initial: number[]; onSave: (ids: number[]) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Sources in this theme" className="max-w-xl">
        {open ? <AddSourcesForm initial={initial} onSave={(ids) => { onSave(ids); onOpenChange(false); }} /> : null}
      </DialogContent>
    </Dialog>
  );
}

function AddSourcesForm({ initial, onSave }: { initial: number[]; onSave: (ids: number[]) => void }) {
  const [selected, setSelected] = useState(initial);
  return (
    <div className="space-y-3">
      <DocumentPicker selected={selected} onChange={setSelected} max={50} />
      <div className="flex justify-end gap-2">
        <DialogClose asChild>
          <Button variant="ghost">Cancel</Button>
        </DialogClose>
        <Button variant="primary" onClick={() => onSave(selected)}>
          Save
        </Button>
      </div>
    </div>
  );
}

function SuggestDialog({ open, onOpenChange, reviewId }: { open: boolean; onOpenChange: (o: boolean) => void; reviewId: number }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Suggest themes" description="Groups papers by how similar their text is (local embeddings, no AI text generation)." className="max-w-xl">
        {open ? <SuggestForm reviewId={reviewId} onDone={() => onOpenChange(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}

function SuggestForm({ reviewId, onDone }: { reviewId: number; onDone: () => void }) {
  const [selected, setSelected] = useState<number[]>([]);
  const [groups, setGroups] = useState<{ name: string; document_ids: number[] }[] | null>(null);
  const [unindexed, setUnindexed] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const mutate = useReviewMutation(reviewId);

  async function suggest() {
    setBusy(true);
    try {
      const result = await reviewService.suggest(reviewId, selected);
      setGroups(result.groups);
      setUnindexed(result.unindexed_document_ids);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not suggest themes");
    } finally {
      setBusy(false);
    }
  }

  async function addAll() {
    for (const group of groups ?? []) {
      await mutate(() => reviewService.addTheme(reviewId, { name: group.name, document_ids: group.document_ids }));
    }
    toast.success(`Added ${pluralize(groups?.length ?? 0, "theme")}`);
    onDone();
  }

  if (groups) {
    return (
      <div className="space-y-3">
        {groups.length === 0 ? <p className="text-[13px] text-muted-foreground">None of the selected papers are indexed for semantic search yet.</p> : null}
        <ol className="space-y-2">
          {groups.map((g, i) => (
            <li key={i} className="rounded-md border border-border p-2.5">
              <Input
                aria-label="Suggested theme name"
                value={g.name}
                onChange={(e) => setGroups(groups.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))}
                className="h-7 text-[13px] font-medium"
              />
              <p className="mt-1 text-xs text-subtle-foreground">{pluralize(g.document_ids.length, "paper")}</p>
            </li>
          ))}
        </ol>
        {unindexed.length ? <p className="text-xs text-warning">{pluralize(unindexed.length, "paper")} could not be grouped because they are not indexed yet.</p> : null}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setGroups(null)}>
            Back
          </Button>
          <Button variant="primary" onClick={addAll} disabled={!groups.length}>
            Add {pluralize(groups.length, "theme")}
          </Button>
        </div>
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <DocumentPicker selected={selected} onChange={setSelected} max={100} />
      <div className="flex justify-end">
        <Button variant="primary" onClick={suggest} disabled={selected.length < 2 || busy}>
          {busy ? <Loader2 className="animate-spin" /> : <Layers />} Suggest groups
        </Button>
      </div>
    </div>
  );
}
