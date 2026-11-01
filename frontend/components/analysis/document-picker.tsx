"use client";

import { Search } from "lucide-react";
import { useState } from "react";

import { DocTypeIcon, formatAuthors } from "@/components/library/shared";
import { Input } from "@/components/ui/form-controls";
import { Skeleton } from "@/components/ui/states";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { useDocuments } from "@/hooks/use-research-data";
import { cn } from "@/lib/utils";

/** Searchable checklist of library documents with a selection limit. */
export function DocumentPicker({
  selected,
  onChange,
  max,
}: {
  selected: number[];
  onChange: (ids: number[]) => void;
  max: number;
}) {
  const [query, setQuery] = useState("");
  const debounced = useDebouncedValue(query.trim(), 200);
  const documents = useDocuments({ q: debounced || undefined, limit: 50 });

  function toggle(id: number) {
    if (selected.includes(id)) onChange(selected.filter((x) => x !== id));
    else if (selected.length < max) onChange([...selected, id]);
  }

  return (
    <div>
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-subtle-foreground" />
        <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Find papers…" className="pl-8" aria-label="Find papers" />
      </div>
      <p className="mt-2 text-xs text-subtle-foreground">
        {selected.length} of max {max} selected
      </p>
      <div className="mt-1 max-h-72 overflow-y-auto rounded-md border border-border">
        {documents.isPending ? (
          <Skeleton className="m-2 h-24" />
        ) : documents.data?.items.length === 0 ? (
          <p className="p-3 text-[13px] text-muted-foreground">No documents found.</p>
        ) : (
          <ul className="divide-y divide-border">
            {documents.data?.items.map((doc) => {
              const checked = selected.includes(doc.id);
              const disabled = !checked && selected.length >= max;
              return (
                <li key={doc.id}>
                  <label
                    className={cn(
                      "flex cursor-pointer items-start gap-2.5 px-3 py-2",
                      checked && "bg-accent-soft/40",
                      disabled && "cursor-not-allowed opacity-50",
                    )}
                  >
                    <input
                      type="checkbox"
                      className="mt-1 accent-[var(--accent)]"
                      checked={checked}
                      disabled={disabled}
                      onChange={() => toggle(doc.id)}
                    />
                    <DocTypeIcon type={doc.doc_type} className="mt-0.5" />
                    <span className="min-w-0">
                      <span className="block truncate text-[13px] font-medium">{doc.title}</span>
                      <span className="block truncate text-xs text-subtle-foreground">
                        {[formatAuthors(doc.authors, 2), doc.publication_year].filter(Boolean).join(" · ") || "—"}
                      </span>
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
