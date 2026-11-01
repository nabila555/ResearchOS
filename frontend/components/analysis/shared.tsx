"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  Download,
  Loader2,
  RotateCcw,
  ShieldAlert,
  Trash2,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { formatPages } from "@/components/library/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useAnalyses } from "@/hooks/use-research-data";
import { cn, formatRelativeTime } from "@/lib/utils";
import { analysisService, reportService } from "@/services/researchos";
import type { Analysis, AnalysisKind, Evidence, FieldStatus, ProfileFieldValue } from "@/types/api";

/** Small page chip linking to the cited page; red when the quote could not be verified. */
export function EvidenceChip({ documentId, evidence }: { documentId: number; evidence: Evidence | null }) {
  if (!evidence) return null;
  const pages = formatPages(evidence.page_start, evidence.page_end) ?? evidence.section ?? "source";
  const title = evidence.verified
    ? `“${evidence.quote}”`
    : `Not verified: ${evidence.reason ?? "unknown reason"}${evidence.quote ? ` — model quoted “${evidence.quote}”` : ""}`;
  const className = cn(
    "ml-1 inline-flex items-center gap-0.5 rounded px-1 py-px align-[1px] font-mono text-[10px] whitespace-nowrap",
    evidence.verified
      ? "bg-accent-soft text-accent-soft-foreground hover:bg-accent hover:text-accent-foreground"
      : "bg-danger-soft text-danger",
  );
  if (!evidence.verified || evidence.page_start === null) {
    return (
      <span className={className} title={title}>
        {!evidence.verified ? <ShieldAlert className="size-2.5" /> : null}
        {evidence.verified ? pages : "unverified"}
      </span>
    );
  }
  return (
    <Link href={`/library/${documentId}?page=${evidence.page_start}`} className={className} title={title}>
      {pages}
    </Link>
  );
}

const FIELD_STATUS: Record<FieldStatus, { label: string; tone: "success" | "warning" | "danger" | "neutral" }> = {
  verified: { label: "Verified", tone: "success" },
  partial: { label: "Partly verified", tone: "warning" },
  unverified: { label: "Unverified", tone: "danger" },
  not_reported: { label: "Not reported", tone: "neutral" },
};

export function FieldStatusBadge({ status }: { status: FieldStatus }) {
  const info = FIELD_STATUS[status];
  return <Badge tone={info.tone}>{info.label}</Badge>;
}

export function FieldStatements({ value, documentId }: { value: ProfileFieldValue | undefined; documentId: number }) {
  if (!value || value.status === "not_reported" || value.statements.length === 0) {
    return <span className="text-[13px] text-subtle-foreground italic">Not reported</span>;
  }
  const single = value.statements.length === 1;
  const items = value.statements.map((s, i) => (
    <span key={i} className={cn(!s.evidence.verified && "text-foreground/60")}>
      {s.text}
      <EvidenceChip documentId={documentId} evidence={s.evidence} />
    </span>
  ));
  return single ? (
    <p className="text-[13px] leading-relaxed">{items[0]}</p>
  ) : (
    <ul className="list-disc space-y-1 pl-4 text-[13px] leading-relaxed">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

const STATUS_ICON = {
  pending: CircleDashed,
  running: Loader2,
  done: CheckCircle2,
  failed: XCircle,
  cancelled: XCircle,
} as const;

/** Progress, errors and actions for a queued/running/finished analysis. */
export function AnalysisStatusCard({ analysis, onChange }: { analysis: Analysis; onChange?: (next: Analysis) => void }) {
  const queryClient = useQueryClient();
  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["analyses"] }),
      queryClient.invalidateQueries({ queryKey: ["analysis", analysis.id] }),
    ]);

  async function act(action: "cancel" | "rerun") {
    try {
      const next = action === "cancel" ? await analysisService.cancel(analysis.id) : await analysisService.rerun(analysis.id);
      await refresh();
      onChange?.(next);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Action failed");
    }
  }

  const active = analysis.status === "pending" || analysis.status === "running";
  const Icon = STATUS_ICON[analysis.status];

  if (analysis.status === "done") {
    return (
      <div className="flex flex-wrap items-center gap-2 text-xs text-subtle-foreground">
        <Badge tone="success">
          <CheckCircle2 className="size-3" /> Done
        </Badge>
        <span>
          {analysis.model} · {formatRelativeTime(analysis.updated_at)}
        </span>
        {analysis.report_id ? (
          <span className="ml-auto flex gap-1">
            <Button asChild size="sm" variant="ghost">
              <a href={analysisService.reportDownloadUrl(analysis.report_id)} download>
                <Download /> Markdown
              </a>
            </Button>
            <Button asChild size="sm" variant="ghost">
              <a href={reportService.pdfUrl(analysis.report_id)} download>
                <Download /> PDF
              </a>
            </Button>
          </span>
        ) : null}
        <Button size="sm" variant="ghost" onClick={() => act("rerun")}>
          <RotateCcw /> Run again
        </Button>
      </div>
    );
  }

  return (
    <Card className="p-4">
      <div className="flex items-start gap-3">
        <Icon
          className={cn(
            "mt-0.5 size-4 shrink-0",
            analysis.status === "running" && "animate-spin text-accent",
            analysis.status === "failed" && "text-danger",
            analysis.status === "pending" && "text-subtle-foreground",
          )}
        />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">
            {analysis.status === "pending"
              ? "Queued"
              : analysis.status === "running"
                ? "Working…"
                : analysis.status === "failed"
                  ? "Analysis failed"
                  : "Cancelled"}
          </p>
          <p className="mt-0.5 text-[13px] text-muted-foreground">
            {analysis.status === "failed" ? analysis.error : analysis.progress_message}
          </p>
          {active ? (
            <>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-surface-muted">
                <div className="h-full bg-accent transition-[width] duration-500" style={{ width: `${Math.max(4, analysis.progress * 100)}%` }} />
              </div>
              <p className="mt-2 text-xs text-subtle-foreground">
                Runs in the background on {analysis.model}; you can leave this page. Local models take about 1 minute per
                step on a CPU.
              </p>
            </>
          ) : null}
        </div>
        {active ? (
          <Button size="sm" onClick={() => act("cancel")}>
            Cancel
          </Button>
        ) : (
          <Button size="sm" onClick={() => act("rerun")}>
            <RotateCcw /> Retry
          </Button>
        )}
      </div>
    </Card>
  );
}

const KIND_STATUS_TONE = { pending: "neutral", running: "accent", done: "success", failed: "danger", cancelled: "neutral" } as const;

/** List of previous runs of one analysis kind. */
export function AnalysisHistory({
  kind,
  selectedId,
  onSelect,
}: {
  kind: AnalysisKind;
  selectedId: number | null;
  onSelect: (id: number | null) => void;
}) {
  const analyses = useAnalyses({ kind });
  const queryClient = useQueryClient();

  async function remove(id: number) {
    try {
      await analysisService.remove(id);
      if (id === selectedId) onSelect(null);
      await queryClient.invalidateQueries({ queryKey: ["analyses"] });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not delete");
    }
  }

  if (!analyses.data?.length) return null;
  return (
    <Card>
      <h2 className="px-4 pt-3 pb-2 text-[13px] font-semibold">Previous runs</h2>
      <ul className="max-h-72 divide-y divide-border overflow-y-auto border-t border-border">
        {analyses.data.map((a) => (
          <li key={a.id} className={cn("group flex items-center gap-2 px-4 py-2", a.id === selectedId && "bg-surface-muted")}>
            <button type="button" className="min-w-0 flex-1 text-left" onClick={() => onSelect(a.id)}>
              <span className="block truncate text-[13px]">{a.title}</span>
              <span className="text-[11px] text-subtle-foreground">{formatRelativeTime(a.created_at)}</span>
            </button>
            <Badge tone={KIND_STATUS_TONE[a.status]}>{a.status}</Badge>
            <button
              type="button"
              onClick={() => remove(a.id)}
              className="hidden rounded p-1 text-subtle-foreground group-hover:block hover:text-danger"
              aria-label={`Delete ${a.title}`}
            >
              <Trash2 className="size-3.5" />
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function AnalysisDisclaimer({ children }: { children: React.ReactNode }) {
  return (
    <p className="flex gap-1.5 text-xs text-muted-foreground">
      <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
      <span>{children}</span>
    </p>
  );
}
