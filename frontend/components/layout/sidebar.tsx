"use client";

import { FlaskConical, Search } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";

import { ThemeToggle } from "@/components/layout/theme-toggle";
import { NAV_ITEMS, isAvailable } from "@/components/layout/navigation";
import { cn } from "@/lib/utils";

function isActive(pathname: string | null, href: string) {
  if (pathname === null) return false;
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

/** Reads the current URL, so it renders inside Suspense (required for prerendering in Next 16). */
function ActiveNavList({ onNavigate }: { onNavigate?: () => void }) {
  return <NavList pathname={usePathname()} onNavigate={onNavigate} />;
}

function NavList({ pathname, onNavigate }: { pathname: string | null; onNavigate?: () => void }) {
  return (
    <ul className="space-y-0.5">
      {NAV_ITEMS.map((item, index) => {
        const active = isActive(pathname, item.href);
        const available = isAvailable(item);
        const Icon = item.icon;
        // Visually separate the workspace items from projects/settings.
        const separated = index === NAV_ITEMS.length - 2;
        return (
          <li key={item.href} className={cn(separated && "mt-3 border-t border-border pt-3")}>
            <Link
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cn(
                "group flex h-8 items-center gap-2.5 rounded-md px-2.5 text-[13px] transition-colors",
                active
                  ? "bg-surface text-foreground font-medium shadow-xs ring-1 ring-border"
                  : "text-muted-foreground hover:bg-surface-muted hover:text-foreground",
              )}
            >
              <Icon className={cn("size-4 shrink-0", active ? "text-accent" : "opacity-80")} aria-hidden />
              <span className="flex-1 truncate">{item.label}</span>
              {!available ? (
                <span
                  className="rounded px-1 font-mono text-[10px] text-subtle-foreground"
                  title={`Planned for phase ${item.phase}`}
                >
                  P{item.phase}
                </span>
              ) : null}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export function SidebarContent({
  onNavigate,
  onSearch,
}: {
  onNavigate?: () => void;
  onSearch: () => void;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-12 items-center gap-2 px-4">
        <div className="flex size-6 items-center justify-center rounded-md bg-accent text-accent-foreground">
          <FlaskConical className="size-3.5" aria-hidden />
        </div>
        <span className="text-sm font-semibold tracking-tight">ResearchOS</span>
      </div>

      <div className="px-2 pt-1">
        <button
          type="button"
          onClick={onSearch}
          className="flex h-8 w-full items-center gap-2 rounded-md border border-border bg-surface px-2.5 text-[13px] text-subtle-foreground shadow-xs transition-colors hover:text-foreground"
        >
          <Search className="size-3.5" aria-hidden />
          <span className="flex-1 text-left">Search</span>
          <kbd className="font-mono text-[10px]">Ctrl K</kbd>
        </button>
      </div>

      <nav aria-label="Main" className="flex-1 overflow-y-auto px-2 py-2">
        <Suspense fallback={<NavList pathname={null} onNavigate={onNavigate} />}>
          <ActiveNavList onNavigate={onNavigate} />
        </Suspense>
      </nav>

      <div className="flex items-center justify-between border-t border-border px-4 py-3">
        <span className="text-[11px] text-subtle-foreground">Local-first · v0.4</span>
        <ThemeToggle />
      </div>
    </div>
  );
}
