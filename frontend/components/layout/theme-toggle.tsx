"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";

import { cn } from "@/lib/utils";

const OPTIONS = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
] as const;

// The chosen theme is only known on the client; render a neutral state on the server.
const subscribe = () => () => {};
function useIsClient() {
  return useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
}

export function ThemeToggle({ showLabels = false }: { showLabels?: boolean }) {
  const { theme, setTheme } = useTheme();
  const isClient = useIsClient();

  return (
    <div
      role="radiogroup"
      aria-label="Colour theme"
      className="inline-flex items-center rounded-md border border-border bg-surface p-0.5"
    >
      {OPTIONS.map(({ value, label, icon: Icon }) => {
        const selected = isClient && theme === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-label={label}
            title={label}
            onClick={() => setTheme(value)}
            className={cn(
              "inline-flex h-6 items-center gap-1.5 rounded px-1.5 text-[12px] transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
              selected
                ? "bg-surface-muted text-foreground"
                : "text-subtle-foreground hover:text-foreground",
            )}
          >
            <Icon className="size-3.5" aria-hidden />
            {showLabels ? <span>{label}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
