"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FilePlus2, FileText, Loader2, Printer, ScrollText, Trash2 } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";

import { DocumentPicker } from "@/components/analysis/document-picker";
import { AnalysisStatusCard } from "@/components/analysis/shared";
import { PageContainer, PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/form-controls";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { useAnalyses, useAnalysis } from "@/hooks/use-research-data";
import { ApiError } from "@/lib/api";
import { cn, formatRelativeTime } from "@/lib/utils";
import { analysisService, reportService } from "@/services/researchos";
import type { AnalysisKind, CitationStyle, ReportType } from "@/types/api";

export const REPORT_LABELS: Record<ReportType, string> = {
  summary: "Research summary",
  literature_review: "Literature review",
  comparison: "Paper comparison",
  methodology: "Methodology analysis",
  gap_analysis: "Research gaps",
  proposal: "Research proposal",
  detective: "Paper Detective",
};

const GENERATORS: { kind: AnalysisKind; label: string; description: string; min: number; max: number }[] = [
  { kind: "summary", label: "Research summary", description: "Structured summary of 1–10 papers from their verified profiles. No extra AI writing.", min: 1, max: 10 },
  { kind: "methodology", label: "Methodology analysis", description: "Designs, data, samples, limitations and reproducibility across 2–15 papers. No extra AI writing.", min: 2, max: 15 },
  { kind: "proposal", label: "Research proposal", description: "AI-drafted proposal from 2–12 papers (optionally a gap analysis). Background cites papers; the rest is labelled as proposal.", min: 2, max: 12 },
];

export function ReportsView() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const selectedId = params.get("id") ? Number(params.get("id")) : null;
  const select = (id: number | null) => router.replace(id ? `${pathname}?id=${id}` : pathname, { scroll: false });
  const [filter, setFilter] = useState<ReportType | "">("");
  const [creating, setCreating] = useState(false);
  const reports = useQuery({ queryKey: ["reports", filter], queryFn: () => reportService.list(filter || undefined) });

  return (
    <PageContainer>
      <PageHeader
        title="Reports"
        description="Every generated report in one place. Read them here, or download them as Markdown or PDF."
        actions={
          <Button variant="primary" onClick={() => setCreating((v) => !v)}>
            <FilePlus2 /> New report
          </Button>
        }
      />
      {creating ? <NewReportPanel onCreated={() => setCreating(false)} onOpen={select} /> : null}
      <div className="grid gap-6 lg:grid-cols-[18rem_1fr]">
        <aside className="space-y-2">
          <Select aria-label="Filter by type" value={filter} onChange={(e) => setFilter(e.target.value as ReportType | "")} className="w-full">
            <option value="">All report types</option>
            {Object.entries(REPORT_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
          {reports.isPending ? (
            <Skeleton className="h-40" />
          ) : reports.isError ? (
            <ErrorState error={reports.error} onRetry={() => reports.refetch()} />
          ) : reports.data.length === 0 ? (
            <p className="px-1 text-xs text-subtle-foreground">No reports yet.</p>
          ) : (
            <ul className="space-y-0.5">
              {reports.data.map((r) => (
                <li key={r.id}>
                  <button
                    type="button"
                    onClick={() => select(r.id)}
                    className={cn("w-full rounded-md px-2.5 py-2 text-left", r.id === selectedId ? "bg-surface-muted" : "hover:bg-surface-muted/60")}
                  >
                    <span className="line-clamp-2 text-[13px] font-medium">{r.title}</span>
                    <span className="text-[11px] text-subtle-foreground">
                      {REPORT_LABELS[r.report_type] ?? r.report_type} · {formatRelativeTime(r.created_at)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>
        <section className="min-w-0">
          {selectedId === null ? (
            <EmptyState
              icon={ScrollText}
              title="Select a report"
              description="Reports are created by Paper Comparison, the Gap Finder, the Paper Detective, saved literature reviews, or “New report”."
              className="py-16"
            />
          ) : (
            <ReportViewer key={selectedId} id={selectedId} onDeleted={() => select(null)} />
          )}
        </section>
      </div>
    </PageContainer>
  );
}

function ReportViewer({ id, onDeleted }: { id: number; onDeleted: () => void }) {
  const report = useQuery({ queryKey: ["report", id], queryFn: () => reportService.get(id) });
  const queryClient = useQueryClient();

  async function remove() {
    if (!window.confirm("Delete this report? The underlying analyses and documents are kept.")) return;
    try {
      await reportService.remove(id);
      await queryClient.invalidateQueries({ queryKey: ["reports"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      onDeleted();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not delete");
    }
  }

  if (report.isError) return <ErrorState error={report.error} onRetry={() => report.refetch()} />;
  if (report.isPending) return <Skeleton className="h-96" />;
  const data = report.data;
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2.5 print:hidden">
        <Badge tone="accent">{REPORT_LABELS[data.report_type] ?? data.report_type}</Badge>
        <span className="text-xs text-subtle-foreground">
          {formatRelativeTime(data.created_at)}
          {data.model_used ? ` · ${data.model_used}` : ""}
        </span>
        <div className="ml-auto flex flex-wrap gap-1">
          <Button asChild size="sm" variant="ghost">
            <a href={reportService.markdownUrl(id)} download>
              <Download /> Markdown
            </a>
          </Button>
          <Button asChild size="sm">
            <a href={reportService.pdfUrl(id)} download>
              <FileText /> PDF
            </a>
          </Button>
          <Button size="sm" variant="ghost" onClick={() => window.print()} aria-label="Print">
            <Printer />
          </Button>
          <Button size="sm" variant="ghost" className="hover:text-danger" onClick={remove} aria-label="Delete report">
            <Trash2 />
          </Button>
        </div>
      </div>
      <CardBody className="pt-4">
        <ReportMarkdown markdown={data.content_markdown} />
      </CardBody>
    </Card>
  );
}

/** Rendered report: GitHub-flavoured Markdown with tables, no raw HTML or images. */
export function ReportMarkdown({ markdown }: { markdown: string }) {
  return (
    <article
      className={cn(
        "max-w-none text-sm leading-relaxed",
        "[&_h1]:mb-3 [&_h1]:text-xl [&_h1]:font-semibold [&_h1]:tracking-tight",
        "[&_h2]:mt-6 [&_h2]:mb-2 [&_h2]:border-b [&_h2]:border-border [&_h2]:pb-1 [&_h2]:text-base [&_h2]:font-semibold",
        "[&_h3]:mt-4 [&_h3]:mb-1 [&_h3]:text-sm [&_h3]:font-semibold",
        "[&_p]:my-2 [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-0.5",
        "[&_hr]:my-4 [&_hr]:border-border [&_a]:text-accent [&_a]:underline",
        "[&_table]:my-3 [&_table]:block [&_table]:overflow-x-auto [&_table]:text-[13px]",
        "[&_th]:border [&_th]:border-border [&_th]:bg-surface-muted [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_th]:align-top",
        "[&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-1 [&_td]:align-top",
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        disallowedElements={["img"]}
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer nofollow">
              {children}
            </a>
          ),
          // The comparison tables use <br> between statements; render them as line breaks.
          td: ({ children }) => <td>{splitBreaks(children)}</td>,
        }}
      >
        {markdown}
      </ReactMarkdown>
    </article>
  );
}

function splitBreaks(children: React.ReactNode): React.ReactNode {
  if (typeof children !== "string") {
    if (Array.isArray(children)) return children.map((c, i) => <span key={i}>{splitBreaks(c)}</span>);
    return children;
  }
  const parts = children.split("<br>");
  return parts.map((part, i) => (
    <span key={i}>
      {part}
      {i < parts.length - 1 ? <br /> : null}
    </span>
  ));
}

function NewReportPanel({ onCreated, onOpen }: { onCreated: () => void; onOpen: (id: number) => void }) {
  const [kind, setKind] = useState<AnalysisKind>("summary");
  const [selection, setSelection] = useState<number[]>([]);
  const [topic, setTopic] = useState("");
  const [gapId, setGapId] = useState<number | "">("");
  const [style, setStyle] = useState<CitationStyle>("apa");
  const [analysisId, setAnalysisId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const gaps = useAnalyses({ kind: "gap_analysis" });
  const analysis = useAnalysis(analysisId);
  const queryClient = useQueryClient();
  const generator = GENERATORS.find((g) => g.kind === kind)!;
  const usesGapPapers = kind === "proposal" && gapId !== "" && selection.length === 0;
  const canStart = usesGapPapers || (selection.length >= generator.min && selection.length <= generator.max);

  useEffect(() => {
    if (analysis.data?.status === "done" && analysis.data.report_id) {
      queryClient.invalidateQueries({ queryKey: ["reports"] });
      onOpen(analysis.data.report_id);
      onCreated();
    }
  }, [analysis.data?.status, analysis.data?.report_id, onCreated, onOpen, queryClient]);

  async function start() {
    setError(null);
    try {
      const created = await analysisService.create({
        kind,
        document_ids: selection,
        style,
        ...(kind === "proposal" ? { topic: topic.trim() || undefined, gap_analysis_id: gapId === "" ? undefined : gapId } : {}),
      });
      setAnalysisId(created.id);
    } catch (e) {
      setError(e instanceof ApiError || e instanceof Error ? e.message : "Could not start");
    }
  }

  return (
    <Card className="mb-6">
      <CardHeader title="New report" description={generator.description} />
      <CardBody className="space-y-4">
        {analysis.data && analysis.data.status !== "done" ? (
          <AnalysisStatusCard analysis={analysis.data} onChange={(next) => setAnalysisId(next.id)} />
        ) : (
          <>
            <div className="flex flex-wrap gap-1 rounded-md bg-surface-muted p-0.5 text-[13px]" role="tablist">
              {GENERATORS.map((g) => (
                <button
                  key={g.kind}
                  type="button"
                  role="tab"
                  aria-selected={kind === g.kind}
                  onClick={() => setKind(g.kind)}
                  className={cn("h-7 flex-1 rounded px-2", kind === g.kind ? "bg-surface font-medium shadow-xs" : "text-muted-foreground")}
                >
                  {g.label}
                </button>
              ))}
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <DocumentPicker selected={selection} onChange={setSelection} max={generator.max} />
              <div className="space-y-3">
                {kind === "proposal" ? (
                  <>
                    <div>
                      <Label htmlFor="proposal-topic">Topic or research interest</Label>
                      <Input id="proposal-topic" value={topic} onChange={(e) => setTopic(e.target.value)} maxLength={300} placeholder="e.g. Sleep and learning in older adults" />
                    </div>
                    <div>
                      <Label htmlFor="proposal-gaps">Build on a gap analysis (optional)</Label>
                      <Select id="proposal-gaps" value={gapId} onChange={(e) => setGapId(e.target.value ? Number(e.target.value) : "")}>
                        <option value="">None</option>
                        {gaps.data
                          ?.filter((g) => g.status === "done")
                          .map((g) => (
                            <option key={g.id} value={g.id}>
                              {g.title}
                            </option>
                          ))}
                      </Select>
                      {usesGapPapers ? <p className="mt-1 text-xs text-subtle-foreground">Uses the papers from that gap analysis.</p> : null}
                    </div>
                  </>
                ) : null}
                <div>
                  <Label htmlFor="report-style">Citation style</Label>
                  <Select id="report-style" value={style} onChange={(e) => setStyle(e.target.value as CitationStyle)}>
                    <option value="apa">APA 7th</option>
                    <option value="mla">MLA 9th</option>
                    <option value="chicago">Chicago</option>
                    <option value="ieee">IEEE</option>
                  </Select>
                </div>
                <p className="text-xs text-subtle-foreground">
                  Papers without a profile are profiled first (about 3 minutes each with a local model); it runs in the
                  background.
                </p>
                {error ? (
                  <p role="alert" className="text-[13px] text-danger">
                    {error}
                  </p>
                ) : null}
                <Button variant="primary" disabled={!canStart} onClick={start}>
                  {analysis.isFetching && analysisId ? <Loader2 className="animate-spin" /> : <FilePlus2 />} Generate {generator.label.toLowerCase()}
                </Button>
              </div>
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}
