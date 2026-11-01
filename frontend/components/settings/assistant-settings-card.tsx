"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Cloud, HardDrive, RefreshCw } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/states";
import { assistantKeys, useAssistantStatus, useInvalidateLibrary } from "@/hooks/use-research-data";
import { cn } from "@/lib/utils";
import { assistantService } from "@/services/researchos";

export function AssistantSettingsCard() {
  const status = useAssistantStatus();
  const queryClient = useQueryClient();
  const invalidateLibrary = useInvalidateLibrary();
  const [saving, setSaving] = useState(false);
  const [reindexing, setReindexing] = useState(false);

  async function save(input: { chat_provider?: string; cloud_consent?: boolean }) {
    setSaving(true);
    try {
      const next = await assistantService.updateSettings(input);
      queryClient.setQueryData(assistantKeys.status, next);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not save settings");
    } finally {
      setSaving(false);
    }
  }

  async function reindex() {
    setReindexing(true);
    try {
      const { queued } = await assistantService.reindex();
      toast.success(queued ? `Queued ${queued} document${queued === 1 ? "" : "s"} for indexing` : "Everything is already indexed");
      await Promise.all([queryClient.invalidateQueries({ queryKey: assistantKeys.status }), invalidateLibrary()]);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not start indexing");
    } finally {
      setReindexing(false);
    }
  }

  if (status.isPending) return <Skeleton className="h-64" />;
  if (status.isError) return null;
  const data = status.data;
  const anthropic = data.providers.find((p) => p.name === "anthropic");
  const index = data.index;
  const percent = index.chunks_total ? Math.round((index.chunks_embedded / index.chunks_total) * 100) : 100;

  return (
    <Card>
      <CardHeader
        title="AI assistant"
        description="Choose where answers are generated. Search embeddings are always computed locally."
      />
      <CardBody className="space-y-5">
        <fieldset disabled={saving}>
          <legend className="mb-2 text-[13px] font-medium">Answer generation</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {data.providers.map((provider) => {
              const selected = data.chat_provider === provider.name;
              return (
                <label
                  key={provider.name}
                  className={cn(
                    "flex cursor-pointer gap-3 rounded-md border p-3 transition-colors",
                    selected ? "border-accent bg-accent-soft/40" : "border-border hover:border-border-strong",
                  )}
                >
                  <input
                    type="radio"
                    name="chat-provider"
                    className="mt-1 accent-[var(--accent)]"
                    checked={selected}
                    onChange={() => save({ chat_provider: provider.name })}
                  />
                  <span className="min-w-0">
                    <span className="flex items-center gap-1.5 text-sm font-medium">
                      {provider.cloud ? <Cloud className="size-3.5" /> : <HardDrive className="size-3.5" />}
                      {provider.label}
                    </span>
                    <span className="block font-mono text-xs text-muted-foreground">{provider.model}</span>
                    <span className="mt-1 block text-xs text-subtle-foreground">
                      {provider.cloud ? "Paid API; sends questions and matching passages." : "Free, private, runs on this computer."}
                    </span>
                  </span>
                </label>
              );
            })}
            {!anthropic ? (
              <div className="rounded-md border border-dashed border-border p-3 text-xs text-subtle-foreground">
                Claude API (optional): set <code className="font-mono">ANTHROPIC_API_KEY</code> in <code className="font-mono">.env</code>{" "}
                and restart the backend to make it selectable.
              </div>
            ) : null}
          </div>

          {anthropic ? (
            <label className="mt-3 flex cursor-pointer gap-2.5 rounded-md border border-border p-3 text-[13px]">
              <input
                type="checkbox"
                className="mt-0.5 accent-[var(--accent)]"
                checked={data.cloud_consent}
                onChange={(e) => save({ cloud_consent: e.target.checked })}
              />
              <span>
                <span className="font-medium">Allow sending questions and retrieved passages to the Claude API</span>
                <span className="mt-0.5 block text-xs text-muted-foreground">
                  Required before the cloud provider can be used. Only the passages matched to each question leave this
                  computer; whole files are never uploaded. You can withdraw consent at any time.
                </span>
              </span>
            </label>
          ) : null}
          {data.chat_provider === "anthropic" && !data.cloud_consent ? (
            <p className="mt-2 text-xs text-warning">The cloud provider is selected but consent is off, so questions will be refused.</p>
          ) : null}
        </fieldset>

        <div>
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-[13px] font-medium">
              Semantic search index <span className="font-mono text-xs font-normal text-muted-foreground">({data.embed_model})</span>
            </p>
            <Button size="sm" onClick={reindex} disabled={reindexing}>
              <RefreshCw className={reindexing ? "animate-spin" : undefined} /> Index missing & failed
            </Button>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-surface-muted">
            <div className="h-full bg-accent transition-[width]" style={{ width: `${percent}%` }} />
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
            <Badge tone="success">{index.ready} ready</Badge>
            {index.pending ? <Badge tone="accent">{index.pending} pending</Badge> : null}
            {index.failed ? <Badge tone="danger">{index.failed} failed</Badge> : null}
            {index.not_indexed ? <Badge>{index.not_indexed} not indexed</Badge> : null}
            <span className="text-subtle-foreground">
              {index.chunks_embedded.toLocaleString("en")} / {index.chunks_total.toLocaleString("en")} passages embedded
            </span>
          </div>
          {index.waiting_for_provider ? (
            <p className="mt-2 text-xs text-warning">Waiting for Ollama: indexing resumes automatically once it is running.</p>
          ) : null}
        </div>
      </CardBody>
    </Card>
  );
}
