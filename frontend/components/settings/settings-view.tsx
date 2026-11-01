"use client";

import { CheckCircle2, CircleAlert, RefreshCw } from "lucide-react";

import { PageContainer, PageHeader } from "@/components/layout/page-header";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ErrorState, Skeleton } from "@/components/ui/states";
import { useSystemStatus } from "@/hooks/use-research-data";
import { API_BASE_URL } from "@/lib/api";
import type { SystemStatus } from "@/types/api";

export function SettingsView() {
  const status = useSystemStatus();

  return (
    <PageContainer>
      <PageHeader
        title="Settings"
        description="Appearance, local storage, and AI provider status."
        actions={
          <Button onClick={() => status.refetch()} disabled={status.isFetching}>
            <RefreshCw className={status.isFetching ? "animate-spin" : undefined} />
            Re-check
          </Button>
        }
      />

      <div className="space-y-6">
        <Card>
          <CardHeader title="Appearance" description="Choose light, dark, or follow your system." />
          <CardBody>
            <ThemeToggle showLabels />
          </CardBody>
        </Card>

        {status.isError ? (
          <ErrorState error={status.error} onRetry={() => status.refetch()} />
        ) : status.isPending ? (
          <>
            <Skeleton className="h-52" />
            <Skeleton className="h-40" />
          </>
        ) : (
          <>
            <AiProviderCard data={status.data} />
            <StorageCard data={status.data} />
          </>
        )}
      </div>
    </PageContainer>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 py-2.5 sm:grid-cols-[200px_1fr] sm:gap-4">
      <dt className="text-[13px] text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-[13px] break-words">{children}</dd>
    </div>
  );
}

function Check({ ok, okText, failText }: { ok: boolean; okText: string; failText: string }) {
  return ok ? (
    <span className="inline-flex items-center gap-1.5 text-success">
      <CheckCircle2 className="size-3.5" /> {okText}
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 text-warning">
      <CircleAlert className="size-3.5" /> {failText}
    </span>
  );
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <code className="rounded bg-surface-muted px-1.5 py-0.5 font-mono text-xs">{children}</code>
  );
}

function AiProviderCard({ data }: { data: SystemStatus }) {
  const { ollama, anthropic, active_provider } = data.ai;
  const missing = [
    !ollama.chat_model_available && ollama.chat_model,
    !ollama.embed_model_available && ollama.embed_model,
  ].filter(Boolean) as string[];

  return (
    <Card>
      <CardHeader
        title="AI providers"
        description="AI features (phase 3+) run locally through Ollama by default. Nothing is sent to a cloud service unless you configure and enable it."
        action={<Badge tone="accent">Active: {active_provider}</Badge>}
      />
      <CardBody>
        <dl className="divide-y divide-border">
          <Row label="Ollama server">
            <Check
              ok={ollama.reachable}
              okText={`Running at ${ollama.base_url}`}
              failText={ollama.error ?? "Not reachable"}
            />
          </Row>
          <Row label="Installed models">
            {ollama.models.length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {ollama.models.map((m) => (
                  <Badge key={m}>{m}</Badge>
                ))}
              </div>
            ) : (
              <span className="text-muted-foreground">None detected</span>
            )}
          </Row>
          <Row label="Chat model">
            <Check
              ok={ollama.chat_model_available}
              okText={ollama.chat_model}
              failText={`${ollama.chat_model} (not installed)`}
            />
          </Row>
          <Row label="Embedding model">
            <Check
              ok={ollama.embed_model_available}
              okText={ollama.embed_model}
              failText={`${ollama.embed_model} (not installed)`}
            />
          </Row>
          <Row label="Claude API (optional)">
            {anthropic.configured ? (
              <span>
                Key configured · model <Code>{anthropic.model}</Code>
              </span>
            ) : (
              <span className="text-muted-foreground">
                Not configured. Optional; set <Code>ANTHROPIC_API_KEY</Code> in <Code>.env</Code>.
              </span>
            )}
          </Row>
        </dl>

        {!ollama.reachable || missing.length > 0 ? (
          <div className="mt-4 rounded-md border border-border bg-surface-muted/60 p-3 text-[13px]">
            <p className="font-medium">Set up local AI (free)</p>
            <ol className="mt-1.5 list-decimal space-y-1 pl-5 text-muted-foreground">
              {!ollama.reachable ? (
                <li>
                  Install Ollama from <Code>ollama.com/download</Code> (or{" "}
                  <Code>winget install Ollama.Ollama</Code>) and start it.
                </li>
              ) : null}
              {(ollama.reachable ? missing : [ollama.chat_model, ollama.embed_model]).map((m) => (
                <li key={m}>
                  <Code>ollama pull {m}</Code>
                </li>
              ))}
              <li>Click “Re-check”.</li>
            </ol>
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}

function StorageCard({ data }: { data: SystemStatus }) {
  return (
    <Card>
      <CardHeader
        title="Local storage"
        description="Documents, embeddings, and the database stay on this machine."
      />
      <CardBody>
        <dl className="divide-y divide-border">
          <Row label="Data directory">
            <Code>{data.storage.data_dir}</Code>
          </Row>
          <Row label="Database">{data.storage.database_backend}</Row>
          <Row label="Upload size limit">{data.storage.max_upload_mb} MB</Row>
          <Row label="Backend API">
            <Code>{API_BASE_URL}</Code> · v{data.version} · {data.environment}
          </Row>
        </dl>
      </CardBody>
    </Card>
  );
}
