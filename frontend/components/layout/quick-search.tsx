"use client";

import { useQuery } from "@tanstack/react-query";
import { CornerDownLeft, Loader2, Search } from "lucide-react";
import { Dialog as DialogPrimitive } from "radix-ui";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { DocTypeIcon, HighlightedSnippet, formatAuthors } from "@/components/library/shared";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { cn } from "@/lib/utils";
import { documentService } from "@/services/researchos";

const RESULT_LIMIT = 8;

/** Global library search, opened with Ctrl/⌘+K or the sidebar button. */
export function QuickSearch({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        onOpenChange(!open);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onOpenChange]);

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/40" />
        <DialogPrimitive.Content className="fixed top-[12vh] left-1/2 z-50 w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 overflow-hidden rounded-lg border border-border bg-surface shadow-2xl outline-none">
          <DialogPrimitive.Title className="sr-only">Search library</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">
            Type to search titles, authors, and full text. Use arrow keys and Enter to open a result.
          </DialogPrimitive.Description>
          {open ? <QuickSearchBody onClose={() => onOpenChange(false)} /> : null}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function QuickSearchBody({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const debounced = useDebouncedValue(query.trim(), 150);
  const results = useQuery({
    queryKey: ["quick-search", debounced],
    queryFn: () => documentService.list({ q: debounced, limit: RESULT_LIMIT }),
    enabled: debounced.length > 0,
  });
  const items = debounced ? (results.data?.items ?? []) : [];

  function open(path: string) {
    onClose();
    router.push(path);
  }

  function onKeyDown(event: React.KeyboardEvent) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((i) => Math.min(i + 1, items.length));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter" && debounced) {
      event.preventDefault();
      const item = items[active];
      open(item ? `/library/${item.id}` : `/library?q=${encodeURIComponent(debounced)}`);
    }
  }

  return (
    <div onKeyDown={onKeyDown}>
      <div className="flex items-center gap-2 border-b border-border px-3">
        {results.isFetching ? (
          <Loader2 className="size-4 animate-spin text-subtle-foreground" />
        ) : (
          <Search className="size-4 text-subtle-foreground" />
        )}
        <input
          autoFocus
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
          }}
          placeholder="Search your library…"
          aria-label="Search your library"
          className="h-11 flex-1 bg-transparent text-sm outline-none placeholder:text-subtle-foreground"
        />
        <kbd className="rounded border border-border px-1.5 font-mono text-[10px] text-subtle-foreground">Esc</kbd>
      </div>

      {debounced ? (
        <ul role="listbox" aria-label="Results" className="max-h-[50vh] overflow-y-auto p-1.5">
          {results.isError ? (
            <li className="px-3 py-6 text-center text-[13px] text-danger">{results.error.message}</li>
          ) : null}
          {results.isSuccess && items.length === 0 ? (
            <li className="px-3 py-6 text-center text-[13px] text-muted-foreground">No matches for “{debounced}”.</li>
          ) : null}
          {items.map((doc, index) => (
            <li key={doc.id} role="option" aria-selected={index === active}>
              <button
                type="button"
                onMouseEnter={() => setActive(index)}
                onClick={() => open(`/library/${doc.id}`)}
                className={cn(
                  "flex w-full gap-2.5 rounded-md px-2.5 py-2 text-left",
                  index === active && "bg-surface-muted",
                )}
              >
                <DocTypeIcon type={doc.doc_type} className="mt-0.5" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{doc.title}</span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {[formatAuthors(doc.authors, 2), doc.publication_year].filter(Boolean).join(" · ")}
                  </span>
                  {doc.snippet ? (
                    <span className="mt-0.5 line-clamp-1 block text-xs text-foreground/75">
                      {doc.match_page ? <span className="mr-1 font-mono text-subtle-foreground">p.{doc.match_page}</span> : null}
                      <HighlightedSnippet text={doc.snippet} />
                    </span>
                  ) : null}
                </span>
              </button>
            </li>
          ))}
          {items.length > 0 ? (
            <li role="option" aria-selected={active === items.length}>
              <button
                type="button"
                onMouseEnter={() => setActive(items.length)}
                onClick={() => open(`/library?q=${encodeURIComponent(debounced)}`)}
                className={cn(
                  "flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-[13px] text-muted-foreground",
                  active === items.length && "bg-surface-muted text-foreground",
                )}
              >
                <CornerDownLeft className="size-3.5" />
                See all {results.data?.total ?? ""} results in the library
              </button>
            </li>
          ) : null}
        </ul>
      ) : (
        <p className="px-4 py-6 text-center text-[13px] text-muted-foreground">
          Search titles, authors, abstracts, and the full text of every document.
        </p>
      )}
    </div>
  );
}
