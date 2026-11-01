"use client";

import {
  Activity as ActivityIcon,
  ArrowRight,
  Cpu,
  FileText,
  FileUp,
  FolderKanban,
  FolderOpen,
  Hash,
  Library,
  Link2,
  MessageSquareText,
  NotebookPen,
  Plus,
  ScrollText,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageContainer, PageHeader } from "@/components/layout/page-header";
import { DOC_TYPE_LABELS, DocTypeIcon } from "@/components/library/shared";
import { ProjectFormDialog } from "@/components/projects/project-form-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { useDashboard, useSystemStatus } from "@/hooks/use-research-data";
import { formatRelativeTime, pluralize } from "@/lib/utils";
import type { DashboardSummary, DocumentType } from "@/types/api";

export function DashboardView() {
  const dashboard = useDashboard();
  const [newProjectOpen, setNewProjectOpen] = useState(false);

  return (
    <PageContainer>
      <PageHeader
        title="Dashboard"
        description="An overview of your research workspace."
        actions={
          <Button variant="primary" onClick={() => setNewProjectOpen(true)}>
            <Plus /> New project
          </Button>
        }
      />
      <ProjectFormDialog open={newProjectOpen} onOpenChange={setNewProjectOpen} />

      {dashboard.isError ? (
        <ErrorState error={dashboard.error} onRetry={() => dashboard.refetch()} />
      ) : dashboard.isPending ? (
        <DashboardSkeleton />
      ) : (
        <DashboardContent data={dashboard.data} onNewProject={() => setNewProjectOpen(true)} />
      )}
    </PageContainer>
  );
}

function DashboardContent({
  data,
  onNewProject,
}: {
  data: DashboardSummary;
  onNewProject: () => void;
}) {
  const { stats } = data;
  const typeBreakdown = Object.entries(stats.documents_by_type)
    .filter(([, n]) => n > 0)
    .map(([type, n]) => `${n} ${DOC_TYPE_LABELS[type as DocumentType]}`)
    .join(" · ");

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          icon={FileText}
          label="Documents"
          value={stats.documents_total}
          hint={typeBreakdown || "No documents yet"}
        />
        <StatCard
          icon={FolderOpen}
          label="Collections"
          value={stats.collections_total}
          hint={pluralize(stats.tags_total, "tag")}
        />
        <StatCard
          icon={FolderKanban}
          label="Active projects"
          value={stats.projects_active}
          hint={`${stats.projects_total} total`}
        />
        <StatCard
          icon={ScrollText}
          label="Reports"
          value={stats.reports_total}
          hint="Generated reports"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader
              title="Recently added"
              description="Latest items in your library"
              action={
                <Link
                  href="/library"
                  className="inline-flex items-center gap-1 text-[13px] text-muted-foreground hover:text-foreground"
                >
                  Library <ArrowRight className="size-3.5" />
                </Link>
              }
            />
            <CardBody>
              {data.recent_documents.length === 0 ? (
                <EmptyState
                  icon={Library}
                  title="Your library is empty"
                  description="Import PDFs, Word files, Markdown, web articles, or write a note. Everything stays on this computer."
                  action={
                    <Button asChild size="sm" variant="primary">
                      <Link href="/library?import=upload">
                        <FileUp /> Import documents
                      </Link>
                    </Button>
                  }
                />
              ) : (
                <ul className="divide-y divide-border">
                  {data.recent_documents.map((doc) => (
                    <li key={doc.id} className="flex items-center gap-3 py-2.5">
                      <DocTypeIcon type={doc.doc_type} />
                      <Link
                        href={`/library/${doc.id}`}
                        className="min-w-0 flex-1 truncate text-sm hover:text-accent"
                      >
                        {doc.title}
                      </Link>
                      <Badge>{DOC_TYPE_LABELS[doc.doc_type]}</Badge>
                      {doc.publication_year ? (
                        <span className="text-xs text-subtle-foreground tabular-nums">
                          {doc.publication_year}
                        </span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Active projects"
              action={
                <Link
                  href="/projects"
                  className="inline-flex items-center gap-1 text-[13px] text-muted-foreground hover:text-foreground"
                >
                  All projects <ArrowRight className="size-3.5" />
                </Link>
              }
            />
            <CardBody>
              {data.active_projects.length === 0 ? (
                <EmptyState
                  icon={FolderKanban}
                  title="No active projects"
                  description="Create a project to frame a research question and gather sources around it."
                  action={
                    <Button size="sm" onClick={onNewProject}>
                      <Plus /> New project
                    </Button>
                  }
                />
              ) : (
                <ul className="divide-y divide-border">
                  {data.active_projects.map((project) => (
                    <li key={project.id} className="py-3">
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="truncate text-sm font-medium">{project.name}</span>
                        <span className="shrink-0 text-xs text-subtle-foreground">
                          updated {formatRelativeTime(project.updated_at)}
                        </span>
                      </div>
                      {project.research_question ? (
                        <p className="mt-0.5 line-clamp-1 text-[13px] text-muted-foreground">
                          {project.research_question}
                        </p>
                      ) : null}
                      <p className="mt-1 text-xs text-subtle-foreground">
                        {pluralize(project.document_count, "source")} ·{" "}
                        {pluralize(project.report_count, "report")}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Quick actions" />
            <CardBody className="space-y-1">
              <QuickAction icon={MessageSquareText} label="Ask your library" href="/assistant" />
              <QuickAction icon={FileUp} label="Import documents" href="/library?import=upload" />
              <QuickAction icon={Link2} label="Import a web article" href="/library?import=url" />
              <QuickAction icon={NotebookPen} label="Write a research note" href="/library?import=note" />
              <QuickAction icon={Plus} label="Start a research project" onClick={onNewProject} />
              <QuickAction icon={Cpu} label="Check local AI setup" href="/settings" />
            </CardBody>
          </Card>

          <AiStatusCard />

          <Card>
            <CardHeader title="Research topics" description="Most-used tags" />
            <CardBody>
              {data.topics.length === 0 ? (
                <p className="text-[13px] text-muted-foreground">
                  Topics appear here once documents are tagged.
                </p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {data.topics.map((topic) => (
                    <Badge key={topic.name} tone="accent">
                      <Hash className="size-3" aria-hidden />
                      {topic.name}
                      <span className="opacity-70">{topic.document_count}</span>
                    </Badge>
                  ))}
                </div>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Recent activity" />
            <CardBody>
              {data.recent_activity.length === 0 ? (
                <p className="text-[13px] text-muted-foreground">No activity yet.</p>
              ) : (
                <ol className="space-y-3">
                  {data.recent_activity.map((item) => (
                    <li key={item.id} className="flex gap-2.5">
                      <ActivityIcon
                        className="mt-0.5 size-3.5 shrink-0 text-subtle-foreground"
                        aria-hidden
                      />
                      <div className="min-w-0">
                        <p className="text-[13px] leading-snug">{item.summary}</p>
                        <time
                          dateTime={item.created_at}
                          className="text-xs text-subtle-foreground"
                        >
                          {formatRelativeTime(item.created_at)}
                        </time>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Recent reports"
              action={
                <Link href="/reports" className="inline-flex items-center gap-1 text-[13px] text-muted-foreground hover:text-foreground">
                  All <ArrowRight className="size-3.5" />
                </Link>
              }
            />
            <CardBody>
              {data.recent_reports.length === 0 ? (
                <p className="text-[13px] text-muted-foreground">
                  Generated summaries, reviews, and gap reports will be listed here.
                </p>
              ) : (
                <ul className="space-y-2">
                  {data.recent_reports.map((report) => (
                    <li key={report.id} className="flex items-center gap-2 text-[13px]">
                      <ScrollText className="size-3.5 text-subtle-foreground" aria-hidden />
                      <Link href={`/reports?id=${report.id}`} className="flex-1 truncate hover:text-accent">
                        {report.title}
                      </Link>
                      <span className="text-xs text-subtle-foreground">
                        {formatRelativeTime(report.created_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number;
  hint: string;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 text-[13px] text-muted-foreground">
        <Icon className="size-3.5" />
        {label}
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">
        {value.toLocaleString("en")}
      </p>
      <p className="mt-0.5 truncate text-xs text-subtle-foreground">{hint}</p>
    </Card>
  );
}

function QuickAction({
  icon: Icon,
  label,
  href,
  onClick,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  href?: string;
  onClick?: () => void;
}) {
  const className =
    "flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-[13px] text-muted-foreground transition-colors hover:bg-surface-muted hover:text-foreground";
  const content = (
    <>
      <Icon className="size-4" />
      <span className="flex-1">{label}</span>
      <ArrowRight className="size-3.5 opacity-50" />
    </>
  );
  return href ? (
    <Link href={href} className={className}>
      {content}
    </Link>
  ) : (
    <button type="button" onClick={onClick} className={className}>
      {content}
    </button>
  );
}

function AiStatusCard() {
  const status = useSystemStatus();
  let tone: "success" | "warning" | "neutral" = "neutral";
  let label = "Checking…";
  let detail = "";

  if (status.isError) {
    label = "Unknown";
    detail = "Backend unavailable.";
  } else if (status.data) {
    const ollama = status.data.ai.ollama;
    if (!ollama.reachable) {
      tone = "warning";
      label = "Ollama not detected";
      detail = "Install and start Ollama to use the AI assistant.";
    } else if (!ollama.chat_model_available || !ollama.embed_model_available) {
      tone = "warning";
      label = "Models missing";
      detail = `Ollama is running with ${pluralize(ollama.models.length, "model")}; configured models are not all installed.`;
    } else {
      tone = "success";
      label = "Ready";
      detail = `${ollama.chat_model} · ${ollama.embed_model}`;
    }
  }

  return (
    <Card>
      <CardHeader
        title="Local AI"
        action={<Badge tone={tone}>{label}</Badge>}
        className="pb-2"
      />
      <CardBody>
        <p className="text-[13px] text-muted-foreground">{detail || " "}</p>
        <Link href="/settings" className="mt-2 inline-block text-[13px] text-accent hover:underline">
          Details
        </Link>
      </CardBody>
    </Card>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading dashboard">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-[92px]" />
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Skeleton className="h-56" />
          <Skeleton className="h-48" />
        </div>
        <div className="space-y-6">
          <Skeleton className="h-36" />
          <Skeleton className="h-28" />
          <Skeleton className="h-40" />
        </div>
      </div>
    </div>
  );
}
