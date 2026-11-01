"use client";

import { useQueryClient } from "@tanstack/react-query";
import { FileSearch2, ScanSearch, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import {
  AnalysisDisclaimer,
  AnalysisStatusCard,
  EvidenceChip,
  FieldStatements,
  FieldStatusBadge,
} from "@/components/analysis/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/states";
import { analysisKeys, useAnalyses, useAnalysis, usePaperProfile } from "@/hooks/use-research-data";
import { ApiError } from "@/lib/api";
import { cn, formatRelativeTime } from "@/lib/utils";
import { analysisService } from "@/services/researchos";
import type { AnalysisKind, DetectiveResult } from "@/types/api";

function useLatest(documentId: number, kind: AnalysisKind) {
  const analyses = useAnalyses({ document_id: documentId });
  return analyses.data?.find((a) => a.kind === kind);
}

function useStart(documentId: number, kind: AnalysisKind) {
  const queryClient = useQueryClient();
  const [starting, setStarting] = useState(false);
  async function start() {
    setStarting(true);
    try {
      await analysisService.create({ kind, document_ids: [documentId] });
      await queryClient.invalidateQueries({ queryKey: ["analyses"] });
    } catch (error) {
      toast.error(error instanceof ApiError || error instanceof Error ? error.message : "Could not start");
    } finally {
      setStarting(false);
    }
  }
  return { start, starting };
}

export function PaperProfileCard({ documentId }: { documentId: number }) {
  const profile = usePaperProfile(documentId);
  const latest = useLatest(documentId, "profile");
  const queryClient = useQueryClient();
  const { start, starting } = useStart(documentId, "profile");
  const active = latest && (latest.status === "pending" || latest.status === "running");

  // Refresh the profile when a background extraction finishes.
  useEffect(() => {
    if (latest?.status === "done") queryClient.invalidateQueries({ queryKey: analysisKeys.profile(documentId) });
  }, [latest?.id, latest?.status, documentId, queryClient]);

  const missing = profile.error instanceof ApiError && profile.error.status === 404;
  const data = profile.data;

  return (
    <Card>
      <CardHeader
        title="Paper profile"
        description="Structured summary extracted by AI. Every statement links to the page it came from."
        action={
          !active ? (
            <Button size="sm" variant={data ? "ghost" : "primary"} onClick={start} disabled={starting}>
              <Sparkles /> {data ? "Re-extract" : "Extract profile"}
            </Button>
          ) : null
        }
      />
      <CardBody className="space-y-4">
        {latest && latest.status !== "done" ? <AnalysisStatusCard analysis={latest} /> : null}
        {profile.isPending ? (
          <Skeleton className="h-24" />
        ) : missing || !data ? (
          !active ? (
            <p className="text-[13px] text-muted-foreground">
              No profile yet. Extraction reads the paper in three passes (overview, methods, results), which takes about
              3 minutes with a local model. Profiles are reused by Paper Comparison and the Gap Finder.
            </p>
          ) : null
        ) : (
          <>
            {data.stale ? (
              <p className="rounded-md bg-warning-soft/60 px-3 py-2 text-xs">
                The document text changed after this profile was made. Re-extract to update it.
              </p>
            ) : null}
            <dl className="divide-y divide-border">
              {data.fields.map((field) => (
                <div key={field.key} className="grid gap-1 py-2.5 sm:grid-cols-[11rem_1fr] sm:gap-4">
                  <dt className="flex items-start justify-between gap-2 text-xs font-medium text-muted-foreground sm:flex-col sm:justify-start">
                    {field.label}
                    {field.status !== "verified" ? <FieldStatusBadge status={field.status} /> : null}
                  </dt>
                  <dd>
                    <FieldStatements value={field} documentId={documentId} />
                  </dd>
                </div>
              ))}
            </dl>
            <p className="text-xs text-subtle-foreground">
              {data.model} · {data.passages_used} passages read · {formatRelativeTime(data.updated_at)}
            </p>
          </>
        )}
      </CardBody>
    </Card>
  );
}

const SEVERITY_TONE = { high: "danger", medium: "warning", low: "neutral" } as const;
const CATEGORY_LABEL: Record<string, string> = {
  unsupported_claim: "Claim may not be fully supported",
  weak_argument: "Weak or incomplete argument",
  methodological_limitation: "Methodological limitation",
  potential_bias: "Potential bias",
  missing_information: "Missing information",
  reproducibility: "Reproducibility",
};
const CHECK_STATUS = {
  reported: { label: "Reported", tone: "success" },
  not_found: { label: "Not found in excerpts", tone: "neutral" },
  unclear: { label: "Unclear", tone: "neutral" },
  unverified: { label: "Claimed, not verified", tone: "danger" },
} as const;

export function DetectiveCard({ documentId }: { documentId: number }) {
  const latest = useLatest(documentId, "detective");
  const { start, starting } = useStart(documentId, "detective");
  // The analyses list omits results; load the finished run in full.
  const full = useAnalysis(latest?.status === "done" ? latest.id : null);
  const result = full.data?.status === "done" ? (full.data.result as DetectiveResult | undefined) : undefined;

  return (
    <Card>
      <CardHeader
        title="Research Paper Detective"
        description="Analytical observations on claims, methods, possible biases and reproducibility. Not accusations."
        action={
          !latest ? (
            <Button size="sm" variant="primary" onClick={start} disabled={starting}>
              <ScanSearch /> Investigate
            </Button>
          ) : null
        }
      />
      <CardBody className="space-y-4">
        {latest && latest.status !== "done" ? <AnalysisStatusCard analysis={latest} /> : null}
        {!latest ? (
          <p className="text-[13px] text-muted-foreground">
            Reviews the key sections of this paper (about 2 minutes locally). Each observation quotes the passage it
            concerns, or is marked as based on something not found in the analysed excerpts.
          </p>
        ) : null}
        {latest?.status === "done" && !result ? <Skeleton className="h-24" /> : null}
        {result ? <DetectiveResults result={result} documentId={documentId} /> : null}
        {latest?.status === "done" ? <AnalysisStatusCard analysis={latest} /> : null}
      </CardBody>
    </Card>
  );
}

function DetectiveResults({ result, documentId }: { result: DetectiveResult; documentId: number }) {
  return (
    <div className="space-y-4">
      {result.observations.length === 0 ? (
        <p className="text-[13px] text-muted-foreground">No observations.</p>
      ) : (
        <ul className="space-y-3">
          {result.observations.map((obs, i) => (
            <li key={i} className={cn("rounded-md border-l-2 pl-3", obs.severity === "high" ? "border-danger" : obs.severity === "medium" ? "border-warning" : "border-border-strong")}>
              <div className="flex flex-wrap items-center gap-1.5">
                <Badge tone={SEVERITY_TONE[obs.severity]}>{obs.severity}</Badge>
                <span className="text-xs text-muted-foreground">{CATEGORY_LABEL[obs.category] ?? obs.category}</span>
              </div>
              <p className="mt-1 text-[13px] leading-relaxed">
                {obs.observation}
                {obs.kind === "quoted" ? <EvidenceChip documentId={documentId} evidence={obs.evidence} /> : null}
              </p>
              {obs.kind === "quoted" && obs.evidence?.verified ? (
                <p className="mt-0.5 text-xs text-subtle-foreground italic">“{obs.evidence.quote}”</p>
              ) : null}
              {obs.kind === "absence" ? (
                <p className="mt-0.5 flex items-center gap-1 text-xs text-subtle-foreground">
                  <FileSearch2 className="size-3" /> Based on absence in the analysed excerpts; the full paper may address it.
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      <div>
        <p className="mb-1.5 text-xs font-medium text-muted-foreground">Reproducibility checklist</p>
        <ul className="grid gap-1.5 sm:grid-cols-2">
          {result.checklist.map((item) => {
            const info = CHECK_STATUS[item.status];
            return (
              <li key={item.key} className="flex items-center justify-between gap-2 rounded-md border border-border px-2.5 py-1.5 text-[13px]">
                <span>{item.label}</span>
                <span className="flex items-center">
                  <Badge tone={info.tone}>{info.label}</Badge>
                  {item.status === "reported" ? <EvidenceChip documentId={documentId} evidence={item.evidence} /> : null}
                </span>
              </li>
            );
          })}
        </ul>
      </div>
      <AnalysisDisclaimer>
        Based on {result.excerpts_analyzed} excerpts. These are prompts for your own critical reading, generated by an AI
        model that can misjudge. They are not verdicts about the paper or its authors.
      </AnalysisDisclaimer>
    </div>
  );
}
