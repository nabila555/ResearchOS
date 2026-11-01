"use client";

import { useQueryClient } from "@tanstack/react-query";
import { GitCompareArrows } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { DocumentPicker } from "@/components/analysis/document-picker";
import {
  AnalysisDisclaimer,
  AnalysisHistory,
  AnalysisStatusCard,
  FieldStatements,
} from "@/components/analysis/shared";
import { PageContainer, PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { useAnalysis } from "@/hooks/use-research-data";
import { ApiError } from "@/lib/api";
import { analysisService } from "@/services/researchos";
import type { ComparisonResult } from "@/types/api";

export function useSelectedAnalysis() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const selectedId = params.get("id") ? Number(params.get("id")) : null;
  const select = (id: number | null) => router.replace(id ? `${pathname}?id=${id}` : pathname, { scroll: false });
  return { selectedId, select };
}

export function CompareView() {
  const { selectedId, select } = useSelectedAnalysis();
  const analysis = useAnalysis(selectedId);
  const queryClient = useQueryClient();
  const [selection, setSelection] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  async function start() {
    setStarting(true);
    setError(null);
    try {
      const created = await analysisService.create({ kind: "comparison", document_ids: selection });
      await queryClient.invalidateQueries({ queryKey: ["analyses"] });
      select(created.id);
    } catch (e) {
      setError(e instanceof ApiError || e instanceof Error ? e.message : "Could not start the comparison");
    } finally {
      setStarting(false);
    }
  }

  return (
    <PageContainer>
      <PageHeader
        title="Paper Comparison"
        description="Compare objectives, methods, samples, findings and limitations side by side. Every cell links to the page it came from."
      />
      <div className="grid gap-6 lg:grid-cols-[20rem_1fr]">
        <aside className="space-y-4">
          <Card>
            <CardHeader title="Choose papers" description="2 to 6 papers" />
            <CardBody className="space-y-3">
              <DocumentPicker selected={selection} onChange={setSelection} max={6} />
              {error ? (
                <p role="alert" className="text-[13px] text-danger">
                  {error}{" "}
                  {error.includes("Settings") ? (
                    <Link href="/settings" className="text-accent hover:underline">
                      Open Settings
                    </Link>
                  ) : null}
                </p>
              ) : null}
              <Button variant="primary" className="w-full" disabled={selection.length < 2 || starting} onClick={start}>
                <GitCompareArrows /> Compare {selection.length || ""} papers
              </Button>
              <p className="text-xs text-subtle-foreground">
                Each paper is profiled once (about 3 minutes locally) and reused by later comparisons and gap analyses.
              </p>
            </CardBody>
          </Card>
          <AnalysisHistory kind="comparison" selectedId={selectedId} onSelect={select} />
        </aside>

        <section className="min-w-0 space-y-4">
          {selectedId === null ? (
            <EmptyState
              icon={GitCompareArrows}
              title="No comparison selected"
              description="Pick at least two papers and start a comparison, or open a previous run."
              className="py-16"
            />
          ) : analysis.isError ? (
            <ErrorState error={analysis.error} onRetry={() => analysis.refetch()} />
          ) : analysis.isPending ? (
            <Skeleton className="h-64" />
          ) : (
            <>
              <h2 className="text-base font-semibold">{analysis.data.title}</h2>
              <AnalysisStatusCard analysis={analysis.data} onChange={(next) => select(next.id)} />
              {analysis.data.status === "done" && analysis.data.result ? (
                <ComparisonTable result={analysis.data.result as ComparisonResult} />
              ) : null}
            </>
          )}
        </section>
      </div>
    </PageContainer>
  );
}

function ComparisonTable({ result }: { result: ComparisonResult }) {
  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-lg border border-border bg-surface">
        <table className="w-full min-w-[640px] border-collapse text-left">
          <thead>
            <tr className="border-b border-border bg-surface-muted/60">
              <th className="sticky left-0 w-40 bg-surface-muted/90 px-3 py-2.5 text-xs font-semibold text-muted-foreground">Aspect</th>
              {result.documents.map((doc) => (
                <th key={doc.id} className="min-w-56 px-3 py-2.5 align-top">
                  <Link href={`/library/${doc.id}`} className="text-[13px] font-semibold hover:text-accent">
                    {doc.title}
                  </Link>
                  <p className="text-xs font-normal text-subtle-foreground">
                    {[doc.authors.slice(0, 2).join(", "), doc.year].filter(Boolean).join(" · ")}
                  </p>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.fields.map((field) => (
              <tr key={field.key} className="border-b border-border last:border-0">
                <th scope="row" className="sticky left-0 bg-surface px-3 py-3 align-top text-xs font-medium text-muted-foreground">
                  {field.label}
                </th>
                {result.documents.map((doc) => (
                  <td key={doc.id} className="px-3 py-3 align-top">
                    <FieldStatements value={result.profiles[String(doc.id)]?.[field.key]} documentId={doc.id} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <AnalysisDisclaimer>
        Page chips link to the supporting passage; hover to see the quote. Faded text marked “unverified” could not be matched
        to the source text and should be checked. “Not reported” means the analysed excerpts don’t state it.
      </AnalysisDisclaimer>
    </div>
  );
}
