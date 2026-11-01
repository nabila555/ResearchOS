"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Check, Copy, Download, Quote, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { PageContainer, PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/form-controls";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { useCollections, useDocuments } from "@/hooks/use-research-data";
import { cn } from "@/lib/utils";
import { citationService } from "@/services/researchos";
import type { CitationStyle, FormattedCitation } from "@/types/api";

const STYLE_LABELS: Record<CitationStyle, string> = {
  apa: "APA 7th",
  mla: "MLA 9th",
  chicago: "Chicago (author-date)",
  ieee: "IEEE",
};

function escapeHtml(text: string) {
  return text.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] as string);
}

/** Copy as rich text (italics survive pasting into Word/Docs) with a plain-text fallback. */
export async function copyCitations(citations: FormattedCitation[], numbered: boolean) {
  const prefix = (c: FormattedCitation) => (numbered && c.number ? `[${c.number}] ` : "");
  const plain = citations.map((c) => prefix(c) + c.text).join("\n\n");
  const html = citations
    .map((c) => `<p>${escapeHtml(prefix(c))}${c.parts.map((p) => (p.italic ? `<i>${escapeHtml(p.text)}</i>` : escapeHtml(p.text))).join("")}</p>`)
    .join("");
  if (typeof ClipboardItem !== "undefined" && navigator.clipboard?.write) {
    await navigator.clipboard.write([
      new ClipboardItem({
        "text/plain": new Blob([plain], { type: "text/plain" }),
        "text/html": new Blob([html], { type: "text/html" }),
      }),
    ]);
  } else {
    await navigator.clipboard.writeText(plain);
  }
}

export function CitationText({ citation }: { citation: FormattedCitation }) {
  return (
    <>
      {citation.parts.map((part, i) => (part.italic ? <i key={i}>{part.text}</i> : <span key={i}>{part.text}</span>))}
    </>
  );
}

export function CitationsView() {
  const [style, setStyle] = useState<CitationStyle>("apa");
  const [collectionId, setCollectionId] = useState<number | "">("");
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [copied, setCopied] = useState<number | "all" | null>(null);
  const collections = useCollections();
  const collectionDocs = useDocuments({ collection_id: collectionId === "" ? undefined : collectionId, limit: 100 });
  const scopeIds = collectionId === "" ? undefined : collectionDocs.data?.items.map((d) => d.id);

  const citations = useQuery({
    queryKey: ["citations", style, scopeIds ?? "all"],
    queryFn: () => citationService.list(style, scopeIds),
    enabled: collectionId === "" || collectionDocs.isSuccess,
  });

  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return (citations.data ?? []).filter((c) => !q || c.text.toLowerCase().includes(q));
  }, [citations.data, filter]);
  const chosen = visible.filter((c) => selected.has(c.document_id));
  const target = chosen.length ? chosen : visible;
  const targetIds = target.map((c) => c.document_id);
  const incomplete = (citations.data ?? []).filter((c) => c.missing.length > 0).length;

  async function copy(list: FormattedCitation[], key: number | "all") {
    try {
      await copyCitations(list, style === "ieee");
      setCopied(key);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      toast.error("Could not access the clipboard");
    }
  }

  function toggle(id: number) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  }

  return (
    <PageContainer>
      <PageHeader
        title="Citation Manager"
        description="Format references from your library in APA, MLA, Chicago or IEEE, copy them, or export BibTeX and RIS."
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Select aria-label="Citation style" value={style} onChange={(e) => setStyle(e.target.value as CitationStyle)} className="w-auto">
          {Object.entries(STYLE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
        <Select aria-label="Scope" value={collectionId} onChange={(e) => setCollectionId(e.target.value ? Number(e.target.value) : "")} className="w-auto">
          <option value="">Whole library</option>
          {collections.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
        <div className="relative min-w-48 flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-subtle-foreground" />
          <Input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter references…" className="pl-8" aria-label="Filter references" />
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-[13px] text-muted-foreground">
          {chosen.length ? `${chosen.length} selected` : `${visible.length} references`}
        </span>
        <div className="ml-auto flex flex-wrap gap-1.5">
          <Button size="sm" onClick={() => copy(target, "all")} disabled={!target.length}>
            {copied === "all" ? <Check /> : <Copy />} Copy bibliography
          </Button>
          {(["bibtex", "ris", "markdown"] as const).map((format) => (
            <Button key={format} asChild size="sm" variant="ghost">
              <a
                href={target.length ? citationService.exportUrl(format, style, targetIds) : undefined}
                aria-disabled={!target.length}
                download
              >
                <Download /> {format === "bibtex" ? "BibTeX" : format === "ris" ? "RIS" : "Markdown"}
              </a>
            </Button>
          ))}
        </div>
      </div>

      {incomplete ? (
        <p className="mb-3 flex items-center gap-1.5 text-xs text-muted-foreground">
          <AlertCircle className="size-3.5 text-warning" />
          {incomplete} reference{incomplete === 1 ? " is" : "s are"} missing details. Missing values are left out, never
          invented; add them with “Edit details” on the document.
        </p>
      ) : null}

      {citations.isError ? (
        <ErrorState error={citations.error} onRetry={() => citations.refetch()} />
      ) : citations.isPending ? (
        <Skeleton className="h-64" />
      ) : visible.length === 0 ? (
        <EmptyState
          icon={Quote}
          title="No references"
          description="Import papers or web articles into the library. Notes are not cited."
          className="py-14"
        />
      ) : (
        <Card className="divide-y divide-border">
          {visible.map((citation) => (
            <div key={citation.document_id} className={cn("flex gap-3 px-4 py-3", selected.has(citation.document_id) && "bg-accent-soft/30")}>
              <input
                type="checkbox"
                className="mt-1 accent-[var(--accent)]"
                checked={selected.has(citation.document_id)}
                onChange={() => toggle(citation.document_id)}
                aria-label="Select reference"
              />
              <div className="min-w-0 flex-1">
                <p className="pl-6 -indent-6 text-sm leading-relaxed">
                  {style === "ieee" && citation.number ? <span className="mr-1 text-muted-foreground">[{citation.number}]</span> : null}
                  <CitationText citation={citation} />
                </p>
                {citation.missing.length ? (
                  <div className="mt-1.5 flex flex-wrap items-center gap-1">
                    <span className="text-xs text-subtle-foreground">Missing:</span>
                    {citation.missing.map((m) => (
                      <Badge key={m} tone="warning">
                        {m}
                      </Badge>
                    ))}
                    <Link href={`/library/${citation.document_id}`} className="ml-1 text-xs text-accent hover:underline">
                      Edit details
                    </Link>
                  </div>
                ) : null}
              </div>
              <Button size="icon" variant="ghost" onClick={() => copy([citation], citation.document_id)} aria-label="Copy citation">
                {copied === citation.document_id ? <Check className="text-success" /> : <Copy />}
              </Button>
            </div>
          ))}
        </Card>
      )}
      <p className="mt-3 text-xs text-subtle-foreground">
        Titles are used exactly as stored. Check capitalisation against your style (APA uses sentence case for article titles).
      </p>
    </PageContainer>
  );
}
