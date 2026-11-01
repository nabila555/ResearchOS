"use client";

import { FlaskConical, Menu } from "lucide-react";
import { Dialog as DialogPrimitive } from "radix-ui";
import { useState } from "react";

import { QuickSearch } from "@/components/layout/quick-search";
import { SidebarContent } from "@/components/layout/sidebar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);

  return (
    <div className="flex min-h-dvh">
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 border-r border-border bg-sidebar md:block">
        <SidebarContent onSearch={() => setSearchOpen(true)} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile top bar */}
        <div className="sticky top-0 z-30 flex h-12 items-center gap-2 border-b border-border bg-background/90 px-4 backdrop-blur md:hidden">
          <DialogPrimitive.Root open={mobileOpen} onOpenChange={setMobileOpen}>
            <DialogPrimitive.Trigger
              className="-ml-1.5 rounded-md p-1.5 text-muted-foreground hover:bg-surface-muted hover:text-foreground"
              aria-label="Open navigation"
            >
              <Menu className="size-5" />
            </DialogPrimitive.Trigger>
            <DialogPrimitive.Portal>
              <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-black/40" />
              <DialogPrimitive.Content className="fixed inset-y-0 left-0 z-50 w-64 border-r border-border bg-sidebar shadow-xl outline-none">
                <DialogPrimitive.Title className="sr-only">Navigation</DialogPrimitive.Title>
                <DialogPrimitive.Description className="sr-only">
                  ResearchOS sections
                </DialogPrimitive.Description>
                <SidebarContent
                  onNavigate={() => setMobileOpen(false)}
                  onSearch={() => {
                    setMobileOpen(false);
                    setSearchOpen(true);
                  }}
                />
              </DialogPrimitive.Content>
            </DialogPrimitive.Portal>
          </DialogPrimitive.Root>
          <FlaskConical className="size-4 text-accent" aria-hidden />
          <span className="text-sm font-semibold tracking-tight">ResearchOS</span>
        </div>

        <main className="flex-1">{children}</main>
        <QuickSearch open={searchOpen} onOpenChange={setSearchOpen} />
      </div>
    </div>
  );
}
