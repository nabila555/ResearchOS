"use client";

import { ChevronDown, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { formatAuthors, formatPages } from "@/components/library/shared";
import { cn } from "@/lib/utils";
import type { SourcePassage } from "@/types/api";

const CITATION = /\[(\s*\d+(?:\s*(?:[,;]|[-–])\s*\d+)*\s*)\]/g;

/** Expand "2, 3" / "4–6" into individual citation numbers. */
export function expandCitation(group: string): number[] {
  const numbers: number[] = [];
  for (const part of group.split(/[,;]/)) {
    const [a, b] = part.split(/[-–]/).map((x) => Number.parseInt(x.trim(), 10));
    if (Number.isInteger(a) && Number.isInteger(b) && b > a && b - a < 20) {
      for (let n = a; n <= b; n++) numbers.push(n);
    } else if (Number.isInteger(a)) {
      numbers.push(a);
    }
  }
  return numbers;
}

/** Turn "[1, 2]" markers into markdown links (#cite-1)(#cite-2) rendered as chips. */
export function linkCitations(markdown: string): string {
  return markdown.replace(CITATION, (_match, group: string) =>
    expandCitation(group)
      .map((n) => `[${n}](#cite-${n})`)
      .join(""),
  );
}

export function sourceHref(source: SourcePassage): string {
  return `/library/${source.document_id}${source.page_start ? `?page=${source.page_start}` : ""}`;
}

interface AnswerContentProps {
  content: string;
  sources: SourcePassage[];
  activeSource: number | null;
  onCite: (n: number) => void;
}

export function AnswerContent({ content, sources, activeSource, onCite }: AnswerContentProps) {
  const known = new Set(sources.map((s) => s.n));
  const components: Components = {
    a({ href, children }) {
      const match = href?.match(/^#cite-(\d+)$/);
      if (match) {
        const n = Number(match[1]);
        const valid = known.has(n);
        return (
          <button
            type="button"
            onClick={() => valid && onCite(n)}
            title={valid ? sources.find((s) => s.n === n)?.title : "Not one of the provided sources (unverified)"}
            className={cn(
              "mx-0.5 inline-flex h-[18px] min-w-[18px] items-center justify-center rounded px-1 align-[1px] font-mono text-[10px] font-medium",
              valid
                ? activeSource === n
                  ? "bg-accent text-accent-foreground"
                  : "bg-accent-soft text-accent-soft-foreground hover:bg-accent hover:text-accent-foreground"
                : "cursor-help bg-danger-soft text-danger line-through",
            )}
          >
            {n}
          </button>
        );
      }
      return (
        <a href={href} target="_blank" rel="noopener noreferrer nofollow" className="text-accent underline">
          {children}
        </a>
      );
    },
  };

  return (
    <div className="prose-answer text-sm leading-relaxed [&_li]:my-0.5 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-2 [&_p:first-child]:mt-0 [&_strong]:font-semibold [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components} disallowedElements={["img"]}>
        {linkCitations(content)}
      </ReactMarkdown>
    </div>
  );
}

export function SourceList({
  sources,
  cited,
  activeSource,
  onSelect,
}: {
  sources: SourcePassage[];
  cited: number[];
  activeSource: number | null;
  onSelect: (n: number | null) => void;
}) {
  const [open, setOpen] = useState(false);
  if (sources.length === 0) return null;
  const citedSet = new Set(cited);
  const expanded = open || activeSource !== null;

  return (
    <div className="mt-3 rounded-md border border-border">
      <button
        type="button"
        onClick={() => {
          setOpen(!expanded);
          if (expanded) onSelect(null);
        }}
        className="flex w-full items-center justify-between px-3 py-2 text-left text-[12px] text-muted-foreground hover:text-foreground"
        aria-expanded={expanded}
      >
        <span>
          {sources.length} source passages · {citedSet.size} cited
        </span>
        <ChevronDown className={cn("size-3.5 transition-transform", expanded && "rotate-180")} />
      </button>
      {expanded ? (
        <ol className="divide-y divide-border border-t border-border">
          {sources.map((source) => (
            <li
              key={source.n}
              id={`source-${source.chunk_id}`}
              className={cn("px-3 py-2.5", activeSource === source.n && "bg-accent-soft/50")}
            >
              <div className="flex items-start gap-2">
                <span
                  className={cn(
                    "mt-0.5 inline-flex h-[18px] min-w-[18px] shrink-0 items-center justify-center rounded px-1 font-mono text-[10px]",
                    citedSet.has(source.n) ? "bg-accent-soft text-accent-soft-foreground" : "bg-surface-muted text-subtle-foreground",
                  )}
                >
                  {source.n}
                </span>
                <div className="min-w-0 flex-1">
                  <Link href={sourceHref(source)} className="text-[13px] font-medium hover:text-accent">
                    {source.title}
                    <ExternalLink className="ml-1 inline size-3 align-[-1px] opacity-60" />
                  </Link>
                  <p className="text-xs text-subtle-foreground">
                    {[
                      formatAuthors(source.authors, 2),
                      source.year,
                      formatPages(source.page_start, source.page_end),
                      source.section,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                    {citedSet.has(source.n) ? "" : " · not cited"}
                  </p>
                  <p
                    className={cn(
                      "mt-1 text-[12px] leading-relaxed text-foreground/80",
                      activeSource !== source.n && "line-clamp-2",
                    )}
                  >
                    {source.text}
                  </p>
                  {activeSource !== source.n ? (
                    <button type="button" className="mt-0.5 text-[11px] text-accent hover:underline" onClick={() => onSelect(source.n)}>
                      Show full passage
                    </button>
                  ) : null}
                </div>
              </div>
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}
