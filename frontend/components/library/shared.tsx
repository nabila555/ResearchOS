import {
  FileCode2,
  FileText,
  FileType2,
  Globe,
  type LucideIcon,
  NotebookPen,
  ScrollText,
} from "lucide-react";
import { Fragment } from "react";

import { cn } from "@/lib/utils";
import type { DocumentType } from "@/types/api";

export const DOC_TYPE_LABELS: Record<DocumentType, string> = {
  pdf: "PDF",
  docx: "Word",
  text: "Text",
  markdown: "Markdown",
  web: "Web",
  note: "Note",
};

export const DOC_TYPE_ICONS: Record<DocumentType, LucideIcon> = {
  pdf: ScrollText,
  docx: FileType2,
  text: FileText,
  markdown: FileCode2,
  web: Globe,
  note: NotebookPen,
};

export const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md", ".markdown"];

export function DocTypeIcon({ type, className }: { type: DocumentType; className?: string }) {
  const Icon = DOC_TYPE_ICONS[type];
  return <Icon className={cn("size-4 shrink-0 text-subtle-foreground", className)} aria-hidden />;
}

/** "Lovelace, Turing & Hopper" style compact author list. */
export function formatAuthors(authors: string[], max = 3): string {
  if (authors.length === 0) return "";
  if (authors.length <= max) return authors.join(", ");
  return `${authors.slice(0, max).join(", ")} et al.`;
}

export function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatPages(start: number | null, end: number | null): string | null {
  if (start === null) return null;
  return end !== null && end !== start ? `pp. ${start}–${end}` : `p. ${start}`;
}

const HIGHLIGHT = /\u0002([\s\S]*?)\u0003/g;

/**
 * Render a search snippet whose matches are wrapped in \u0002 … \u0003 by the
 * backend. Everything is rendered as text, so snippets cannot inject markup.
 */
export function HighlightedSnippet({ text, className }: { text: string; className?: string }) {
  const parts: { text: string; mark: boolean }[] = [];
  let last = 0;
  for (const match of text.matchAll(HIGHLIGHT)) {
    if (match.index > last) parts.push({ text: text.slice(last, match.index), mark: false });
    parts.push({ text: match[1], mark: true });
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push({ text: text.slice(last), mark: false });

  return (
    <span className={className}>
      {parts.map((part, i) =>
        part.mark ? (
          <mark key={i} className="rounded-sm bg-warning-soft px-0.5 text-foreground">
            {part.text}
          </mark>
        ) : (
          <Fragment key={i}>{part.text.replace(/[\u0002\u0003]/g, "")}</Fragment>
        ),
      )}
    </span>
  );
}
