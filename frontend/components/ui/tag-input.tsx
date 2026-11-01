"use client";

import { X } from "lucide-react";
import { useId, useState } from "react";

import { cn } from "@/lib/utils";

interface TagInputProps {
  value: string[];
  onChange: (tags: string[]) => void;
  suggestions?: string[];
  placeholder?: string;
  disabled?: boolean;
  id?: string;
  className?: string;
}

/** Chip-style tag editor. Enter or comma adds a tag; Backspace on empty input removes the last. */
export function TagInput({
  value,
  onChange,
  suggestions = [],
  placeholder = "Add tag…",
  disabled,
  id,
  className,
}: TagInputProps) {
  const [draft, setDraft] = useState("");
  const listId = useId();

  function add(raw: string) {
    const tag = raw.trim().replace(/^#/, "").replace(/\s+/g, " ");
    setDraft("");
    if (!tag || value.some((t) => t.toLowerCase() === tag.toLowerCase())) return;
    onChange([...value, tag]);
  }

  return (
    <div
      className={cn(
        "flex min-h-8 w-full flex-wrap items-center gap-1 rounded-md border border-border bg-surface px-1.5 py-1 shadow-xs focus-within:border-accent focus-within:ring-2 focus-within:ring-ring",
        disabled && "opacity-50",
        className,
      )}
    >
      {value.map((tag) => (
        <span
          key={tag}
          className="inline-flex items-center gap-0.5 rounded bg-accent-soft py-0.5 pr-0.5 pl-1.5 text-xs text-accent-soft-foreground"
        >
          {tag}
          <button
            type="button"
            onClick={() => onChange(value.filter((t) => t !== tag))}
            disabled={disabled}
            className="rounded p-0.5 hover:bg-accent/15"
            aria-label={`Remove tag ${tag}`}
          >
            <X className="size-3" />
          </button>
        </span>
      ))}
      <input
        id={id}
        list={suggestions.length ? listId : undefined}
        value={draft}
        disabled={disabled}
        onChange={(e) => {
          const next = e.target.value;
          if (next.endsWith(",")) add(next.slice(0, -1));
          else setDraft(next);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            add(draft);
          } else if (e.key === "Backspace" && !draft && value.length) {
            onChange(value.slice(0, -1));
          }
        }}
        onBlur={() => draft && add(draft)}
        placeholder={value.length ? "" : placeholder}
        className="h-6 min-w-24 flex-1 bg-transparent px-1 text-sm outline-none placeholder:text-subtle-foreground"
        maxLength={100}
      />
      {suggestions.length ? (
        <datalist id={listId}>
          {suggestions
            .filter((s) => !value.some((v) => v.toLowerCase() === s.toLowerCase()))
            .map((s) => (
              <option key={s} value={s} />
            ))}
        </datalist>
      ) : null}
    </div>
  );
}
