"use client";

import { useQueryClient } from "@tanstack/react-query";
import { BookOpenCheck, Lightbulb, ScanSearch } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { useSelectedAnalysis } from "@/components/analysis/compare-view";
import { DocumentPicker } from "@/components/analysis/document-picker";
import { AnalysisDisclaimer, AnalysisHistory, AnalysisStatusCard } from "@/components/analysis/shared";
import { PageContainer, PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/form-controls";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { useAnalysis, useCollections } from "@/hooks/use-research-data";
import { cn } from "@/lib/utils";
import { analysisService } from "@/services/researchos";
import type { GapItem, GapResult } from "@/types/api";

export function GapsView() {
  const { selectedId, select } = useSelectedAnalysis();
  const analysis = useAnalysis(selectedId);
  const collections = useCollections();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"collection" | "papers">("collection");
  const [collectionId, setCollectionId] = useState<number | "">("");
  const [selection, setSelection] = useState<number[]>([]);
  const [focus, setFocus] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const canStart = mode === "collection" ? collectionId !== "" : selection.length >= 2;

  async function start() {
    setStarting(true);
    setError(null);
    try {
      const created = await analysisService.create({
        kind: "gap_analysis",
        ...(mode === "collection" ? { collection_id: Number(collectionId) } : { document_ids: selection }),
        focus: focus.trim() || undefined,
      });
      await queryClient.invalidateQueries({ queryKey: ["analyses"] });
      select(created.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the analysis");
    } finally {
      setStarting(false);
    }
  }

  return (
    <PageContainer>
      <PageHeader
        title="Research Gap Finder"
        description="Find underexplored areas, contradictions and open questions. Literature-supported findings are kept separate from AI hypotheses."
      />
      <div className="grid gap-6 lg:grid-cols-[20rem_1fr]">
        <aside className="space-y-4">
          <Card>
            <CardHeader title="What to analyse" description="2 to 12 papers" />
            <CardBody className="space-y-3">
              <div role="tablist" className="flex gap-1 rounded-md bg-surface-muted p-0.5 text-[13px]">
                {(["collection", "papers"] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    role="tab"
                    aria-selected={mode === m}
                    onClick={() => setMode(m)}
                    className={cn("h-7 flex-1 rounded", mode === m ? "bg-surface font-medium shadow-xs" : "text-muted-foreground")}
                  >
                    {m === "collection" ? "A collection" : "Pick papers"}
                  </button>
                ))}
              </div>
              {mode === "collection" ? (
                <div>
                  <Label htmlFor="gap-collection">Collection</Label>
                  <Select id="gap-collection" value={collectionId} onChange={(e) => setCollectionId(e.target.value ? Number(e.target.value) : "")}>
                    <option value="">Choose…</option>
                    {collections.data?.map((c) => (
                      <option key={c.id} value={c.id} disabled={c.document_count < 2}>
                        {c.name} ({c.document_count})
                      </option>
                    ))}
                  </Select>
                  {collections.data?.length === 0 ? (
                    <p className="mt-1.5 text-xs text-subtle-foreground">
                      No collections yet. <Link href="/library" className="text-accent hover:underline">Create one in the library</Link>{" "}
                      or pick papers.
                    </p>
                  ) : null}
                </div>
              ) : (
                <DocumentPicker selected={selection} onChange={setSelection} max={12} />
              )}
              <div>
                <Label htmlFor="gap-focus">Focus (optional)</Label>
                <Input id="gap-focus" value={focus} onChange={(e) => setFocus(e.target.value)} maxLength={300} placeholder="e.g. effects in older adults" />
              </div>
              {error ? (
                <p role="alert" className="text-[13px] text-danger">
                  {error}
                </p>
              ) : null}
              <Button variant="primary" className="w-full" disabled={!canStart || starting} onClick={start}>
                <ScanSearch /> Find research gaps
              </Button>
            </CardBody>
          </Card>
          <AnalysisHistory kind="gap_analysis" selectedId={selectedId} onSelect={select} />
        </aside>

        <section className="min-w-0 space-y-4">
          {selectedId === null ? (
            <EmptyState icon={ScanSearch} title="No analysis selected" description="Choose papers and run the gap finder, or open a previous run." className="py-16" />
          ) : analysis.isError ? (
            <ErrorState error={analysis.error} onRetry={() => analysis.refetch()} />
          ) : analysis.isPending ? (
            <Skeleton className="h-64" />
          ) : (
            <>
              <h2 className="text-base font-semibold">{analysis.data.title}</h2>
              <AnalysisStatusCard analysis={analysis.data} onChange={(next) => select(next.id)} />
              {analysis.data.status === "done" && analysis.data.result ? <GapResults result={analysis.data.result as GapResult} /> : null}
            </>
          )}
        </section>
      </div>
    </PageContainer>
  );
}

function GapResults({ result }: { result: GapResult }) {
  const [filter, setFilter] = useState<"all" | "literature" | "hypothesis">("all");
  return (
    <div className="space-y-4">
      <Card>
        <CardBody className="pt-4">
          <p className="mb-2 text-xs font-medium text-muted-foreground">Papers analysed{result.focus ? ` · focus: ${result.focus}` : ""}</p>
          <ul className="space-y-1">
            {result.papers.map((p) => (
              <li key={p.label} className="text-[13px]">
                <span className="mr-1.5 font-mono text-xs text-subtle-foreground">{p.label}</span>
                <Link href={`/library/${p.document_id}`} className="hover:text-accent">
                  {p.title}
                </Link>
                {p.year ? <span className="text-subtle-foreground"> ({p.year})</span> : null}
              </li>
            ))}
          </ul>
        </CardBody>
      </Card>

      <div className="flex flex-wrap items-center gap-1.5 text-[13px]">
        {(["all", "literature", "hypothesis"] as const).map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={cn("h-7 rounded-md px-2.5", filter === f ? "bg-surface-muted font-medium" : "text-muted-foreground hover:text-foreground")}
          >
            {f === "all" ? "All" : f === "literature" ? "Supported by literature" : "AI hypotheses"}
          </button>
        ))}
      </div>

      {result.categories.map((category) => {
        const items = category.items.filter((i) => filter === "all" || i.basis === filter);
        return (
          <Card key={category.key}>
            <CardHeader title={category.label} />
            <CardBody>
              {items.length === 0 ? (
                <p className="text-[13px] text-subtle-foreground">Nothing identified{filter !== "all" ? " for this filter" : ""}.</p>
              ) : (
                <ul className="space-y-3">
                  {items.map((item, i) => (
                    <GapItemRow key={i} item={item} />
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        );
      })}
      <AnalysisDisclaimer>
        “Supported by literature” means the cited papers’ verified summaries back the point; open the papers to confirm.
        AI hypotheses are suggestions to investigate, not findings.
      </AnalysisDisclaimer>
    </div>
  );
}

function GapItemRow({ item }: { item: GapItem }) {
  const literature = item.basis === "literature";
  return (
    <li className={cn("rounded-md border-l-2 pl-3", literature ? "border-success" : "border-warning")}>
      <div className="flex flex-wrap items-center gap-1.5">
        {literature ? (
          <Badge tone="success">
            <BookOpenCheck className="size-3" /> Literature
          </Badge>
        ) : (
          <Badge tone="warning">
            <Lightbulb className="size-3" /> AI hypothesis
          </Badge>
        )}
        {item.papers.map((p) => (
          <Link key={p.label} href={`/library/${p.document_id}`} title={p.title}>
            <Badge className="font-mono hover:text-foreground">{p.label}</Badge>
          </Link>
        ))}
      </div>
      <p className="mt-1 text-sm">{item.statement}</p>
      {item.rationale ? <p className="mt-0.5 text-[13px] text-muted-foreground">{item.rationale}</p> : null}
      {item.notes.map((note) => (
        <p key={note} className="mt-0.5 text-xs text-warning">
          {note}
        </p>
      ))}
    </li>
  );
}
