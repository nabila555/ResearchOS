import { ArrowRight, CircleDashed } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PageContainer, PageHeader } from "@/components/layout/page-header";
import { CURRENT_PHASE, findNavItem } from "@/components/layout/navigation";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

/**
 * Honest placeholder for sections that are on the roadmap but not built yet.
 * It describes what is planned instead of rendering non-functional controls.
 */
export function PlannedFeature({ href }: { href: string }) {
  const item = findNavItem(href);
  if (!item) notFound();
  const Icon = item.icon;

  return (
    <PageContainer>
      <PageHeader title={item.label} description={item.summary} />
      <Card className="p-6">
        <div className="flex items-start gap-4">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-surface-muted">
            <Icon className="size-5 text-muted-foreground" aria-hidden />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-sm font-semibold">Not built yet</h2>
              <Badge tone="accent">Phase {item.phase}</Badge>
            </div>
            <p className="mt-1 text-[13px] text-muted-foreground">
              ResearchOS is built incrementally. The current release completes phase{" "}
              {CURRENT_PHASE}; this section ships in phase {item.phase} and will include:
            </p>
            <ul className="mt-4 space-y-2">
              {item.planned.map((line) => (
                <li key={line} className="flex gap-2 text-sm">
                  <CircleDashed
                    className="mt-0.5 size-4 shrink-0 text-subtle-foreground"
                    aria-hidden
                  />
                  <span>{line}</span>
                </li>
              ))}
            </ul>
            <Link
              href="/projects"
              className="mt-6 inline-flex items-center gap-1 text-[13px] font-medium text-accent hover:underline"
            >
              Meanwhile, set up a research project <ArrowRight className="size-3.5" />
            </Link>
          </div>
        </div>
      </Card>
    </PageContainer>
  );
}
