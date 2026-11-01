"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowUp,
  BadgeCheck,
  CircleHelp,
  Info,
  Loader2,
  MessageSquarePlus,
  MessageSquareText,
  ShieldAlert,
  Square,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { AnswerContent, SourceList } from "@/components/assistant/answer-content";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/form-controls";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import {
  assistantKeys,
  useAssistantStatus,
  useChatSession,
  useChatSessions,
  useCollections,
  useProjects,
  useSystemStatus,
} from "@/hooks/use-research-data";
import { ApiError } from "@/lib/api";
import { cn, formatRelativeTime } from "@/lib/utils";
import { assistantService } from "@/services/researchos";
import type { ChatMessage, ChatScope, SourcePassage } from "@/types/api";

const EXAMPLE_QUESTIONS = [
  "What are the main findings across these papers?",
  "Which methodologies are used, and with what sample sizes?",
  "What limitations do the authors report?",
  "Where do the studies disagree?",
];

interface StreamingState {
  question: string;
  sources: SourcePassage[];
  notes: string[];
  text: string;
  phase: "retrieving" | "generating";
}

function scopeToValue(scope: ChatScope | undefined): string {
  if (scope?.collection_id) return `c:${scope.collection_id}`;
  if (scope?.project_id) return `p:${scope.project_id}`;
  return "all";
}

function valueToScope(value: string): ChatScope {
  const [kind, id] = value.split(":");
  if (kind === "c") return { collection_id: Number(id) };
  if (kind === "p") return { project_id: Number(id) };
  return {};
}

export function AssistantView() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const selectedId = params.get("chat") ? Number(params.get("chat")) : null;

  const sessions = useChatSessions();
  const session = useChatSession(selectedId);
  const status = useAssistantStatus();
  const system = useSystemStatus();
  const collections = useCollections();
  const projects = useProjects();

  const [draft, setDraft] = useState("");
  const [scopeValue, setScopeValue] = useState<string | null>(null);
  const [streaming, setStreaming] = useState<StreamingState | null>(null);
  const [requestError, setRequestError] = useState<ApiError | Error | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // The scope shown is the user's pending choice, else the chat's saved scope.
  const effectiveScopeValue = scopeValue ?? scopeToValue(session.data?.scope);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [streaming?.text, streaming?.phase, session.data?.messages.length]);

  function selectChat(id: number | null) {
    abortRef.current?.abort();
    setScopeValue(null);
    setRequestError(null);
    router.replace(id ? `${pathname}?chat=${id}` : pathname, { scroll: false });
  }

  async function send(question: string) {
    const content = question.trim();
    if (!content || streaming) return;
    setRequestError(null);
    let sessionId = selectedId;
    const scope = valueToScope(effectiveScopeValue);
    try {
      if (sessionId === null) {
        const created = await assistantService.createSession(scope);
        sessionId = created.id;
        selectChat(created.id);
      }
    } catch (error) {
      setRequestError(error as Error);
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;
    setDraft("");
    setStreaming({ question: content, sources: [], notes: [], text: "", phase: "retrieving" });
    try {
      await assistantService.ask(
        sessionId,
        content,
        scopeValue !== null ? scope : undefined,
        (event) => {
          if (event.type === "sources") {
            setStreaming((s) => s && { ...s, sources: event.sources, notes: event.notes, phase: "generating" });
          } else if (event.type === "delta") {
            setStreaming((s) => s && { ...s, text: s.text + event.text });
          } else if (event.type === "error") {
            toast.error(event.message);
          }
        },
        controller.signal,
      );
    } catch (error) {
      if (!controller.signal.aborted) {
        setRequestError(error as Error);
        if (error instanceof ApiError && error.status && error.status >= 400) setDraft(content);
      }
    } finally {
      abortRef.current = null;
      setScopeValue(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: assistantKeys.session(sessionId) }),
        queryClient.invalidateQueries({ queryKey: assistantKeys.sessions }),
      ]);
      setStreaming(null);
    }
  }

  async function deleteChat(id: number) {
    try {
      await assistantService.deleteSession(id);
      if (id === selectedId) selectChat(null);
      await queryClient.invalidateQueries({ queryKey: assistantKeys.sessions });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not delete chat");
    }
  }

  const messages = session.data?.messages ?? [];
  const libraryEmpty = status.data?.index.documents_total === 0;

  return (
    <div className="flex h-[calc(100dvh-3rem)] md:h-dvh">
      {/* Chat list */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-border lg:flex">
        <div className="p-3">
          <Button className="w-full" onClick={() => selectChat(null)}>
            <MessageSquarePlus /> New chat
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 pb-3">
          {sessions.isPending ? (
            <Skeleton className="h-24" />
          ) : sessions.data?.length === 0 ? (
            <p className="px-2 text-xs text-subtle-foreground">No chats yet.</p>
          ) : (
            <ul className="space-y-0.5">
              {sessions.data?.map((s) => (
                <li key={s.id} className="group relative">
                  <button
                    type="button"
                    onClick={() => selectChat(s.id)}
                    className={cn(
                      "w-full rounded-md px-2.5 py-2 pr-8 text-left transition-colors",
                      s.id === selectedId ? "bg-surface-muted" : "hover:bg-surface-muted/60",
                    )}
                  >
                    <span className="line-clamp-2 text-[13px] leading-snug">{s.title}</span>
                    <span className="text-[11px] text-subtle-foreground">
                      {formatRelativeTime(s.last_message_at ?? s.updated_at)}
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => deleteChat(s.id)}
                    className="absolute top-2 right-1.5 hidden rounded p-1 text-subtle-foreground group-hover:block hover:text-danger"
                    aria-label={`Delete chat ${s.title}`}
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>

      {/* Conversation */}
      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-2.5 sm:px-6">
          <div className="min-w-0">
            <h1 className="truncate text-sm font-semibold">{session.data?.title ?? "AI Assistant"}</h1>
            <p className="text-xs text-subtle-foreground">Answers come only from your library, with citations.</p>
          </div>
          <div className="flex items-center gap-2">
            <ProviderBadge />
            {/* The chat list sidebar is hidden on small screens; offer a picker instead. */}
            {sessions.data?.length ? (
              <Select
                aria-label="Open chat"
                value={selectedId ?? ""}
                onChange={(e) => selectChat(e.target.value ? Number(e.target.value) : null)}
                className="h-7 w-32 text-xs lg:hidden"
              >
                <option value="">New chat</option>
                {sessions.data.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.title}
                  </option>
                ))}
              </Select>
            ) : null}
            <Button size="sm" className="lg:hidden" onClick={() => selectChat(null)} aria-label="New chat">
              <MessageSquarePlus />
            </Button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-3xl space-y-6 px-4 py-6 sm:px-6">
            <ReadinessNotices />
            {session.isError ? (
              <ErrorState error={session.error} onRetry={() => session.refetch()} />
            ) : selectedId !== null && session.isPending ? (
              <Skeleton className="h-40" />
            ) : messages.length === 0 && !streaming ? (
              libraryEmpty ? (
                <EmptyState
                  icon={MessageSquareText}
                  title="Your library is empty"
                  description="The assistant only answers from your own documents. Import some papers first."
                  action={
                    <Link href="/library?import=upload" className="text-[13px] font-medium text-accent hover:underline">
                      Import documents
                    </Link>
                  }
                  className="py-14"
                />
              ) : (
                <div className="py-8 text-center">
                  <MessageSquareText className="mx-auto size-6 text-subtle-foreground" />
                  <h2 className="mt-3 text-base font-semibold">Ask your research library</h2>
                  <p className="mx-auto mt-1 max-w-md text-[13px] text-muted-foreground">
                    Every claim is linked to the passage and page it came from. When your sources don’t
                    cover a question, the assistant says so instead of guessing.
                  </p>
                  <div className="mx-auto mt-5 grid max-w-xl gap-2 sm:grid-cols-2">
                    {EXAMPLE_QUESTIONS.map((q) => (
                      <button
                        key={q}
                        type="button"
                        onClick={() => setDraft(q)}
                        className="rounded-md border border-border bg-surface px-3 py-2 text-left text-[13px] text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              )
            ) : (
              <>
                {messages.map((m) =>
                  m.role === "user" ? <UserBubble key={m.id} text={m.content} /> : <AssistantMessage key={m.id} message={m} />,
                )}
                {streaming ? (
                  <>
                    {messages.at(-1)?.content !== streaming.question ? <UserBubble text={streaming.question} /> : null}
                    <StreamingMessage state={streaming} />
                  </>
                ) : null}
              </>
            )}
            {requestError ? <RequestError error={requestError} /> : null}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* Composer */}
        <form
          className="border-t border-border bg-background px-4 py-3 sm:px-6"
          onSubmit={(e) => {
            e.preventDefault();
            send(draft);
          }}
        >
          <div className="mx-auto w-full max-w-3xl">
            <div className="rounded-lg border border-border bg-surface shadow-xs focus-within:border-accent focus-within:ring-2 focus-within:ring-ring">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send(draft);
                  }
                }}
                rows={2}
                maxLength={4000}
                placeholder="Ask a question about your sources…"
                aria-label="Question"
                className="block w-full resize-none bg-transparent px-3 pt-2.5 text-sm outline-none placeholder:text-subtle-foreground"
                disabled={libraryEmpty}
              />
              <div className="flex items-center justify-between gap-2 px-2 pb-2">
                <Select
                  aria-label="Search scope"
                  value={effectiveScopeValue}
                  onChange={(e) => setScopeValue(e.target.value)}
                  className="h-7 w-auto max-w-[60%] border-transparent bg-surface-muted text-xs shadow-none"
                >
                  <option value="all">Whole library</option>
                  {collections.data?.length ? (
                    <optgroup label="Collection">
                      {collections.data.map((c) => (
                        <option key={c.id} value={`c:${c.id}`}>
                          {c.name} ({c.document_count})
                        </option>
                      ))}
                    </optgroup>
                  ) : null}
                  {projects.data?.length ? (
                    <optgroup label="Project">
                      {projects.data.map((p) => (
                        <option key={p.id} value={`p:${p.id}`}>
                          {p.name} ({p.document_count})
                        </option>
                      ))}
                    </optgroup>
                  ) : null}
                </Select>
                {streaming ? (
                  <Button type="button" size="sm" onClick={() => abortRef.current?.abort()}>
                    <Square className="fill-current" /> Stop
                  </Button>
                ) : (
                  <Button type="submit" size="sm" variant="primary" disabled={!draft.trim() || libraryEmpty} aria-label="Send">
                    <ArrowUp />
                  </Button>
                )}
              </div>
            </div>
            <p className="mt-1.5 text-center text-[11px] text-subtle-foreground">
              {system.data?.ai.ollama.reachable === false && status.data?.chat_provider === "ollama"
                ? "Ollama is not running."
                : "Local models can still make mistakes. Check important claims against the cited passages."}
            </p>
          </div>
        </form>
      </section>
    </div>
  );
}

function ProviderBadge() {
  const status = useAssistantStatus();
  const provider = status.data?.providers.find((p) => p.name === status.data?.chat_provider);
  if (!provider) return null;
  return (
    <Link href="/settings" title="Change in Settings">
      <Badge tone={provider.cloud ? "warning" : "neutral"}>
        {provider.cloud ? "Cloud" : "Local"} · {provider.model}
      </Badge>
    </Link>
  );
}

function ReadinessNotices() {
  const status = useAssistantStatus();
  const system = useSystemStatus();
  const notices: { tone: "warning" | "info"; text: React.ReactNode }[] = [];
  const ollama = system.data?.ai.ollama;
  const usingLocal = status.data?.chat_provider === "ollama";

  if (ollama && !ollama.reachable) {
    notices.push({
      tone: "warning",
      text: (
        <>
          Ollama is not running, so {usingLocal ? "answers and " : ""}semantic search are unavailable.{" "}
          <Link href="/settings" className="text-accent hover:underline">
            Setup help
          </Link>
        </>
      ),
    });
  } else if (ollama && usingLocal && !ollama.chat_model_available) {
    notices.push({
      tone: "warning",
      text: (
        <>
          The chat model <code className="font-mono text-xs">{ollama.chat_model}</code> is not installed. Run{" "}
          <code className="font-mono text-xs">ollama pull {ollama.chat_model}</code>.
        </>
      ),
    });
  }
  const index = status.data?.index;
  if (index && index.pending > 0) {
    notices.push({
      tone: "info",
      text: `Indexing ${index.pending} document${index.pending === 1 ? "" : "s"} for semantic search${
        index.waiting_for_provider ? " (waiting for Ollama)" : ""
      }. Keyword search covers them until it finishes.`,
    });
  }
  if (index && index.failed > 0) {
    notices.push({
      tone: "warning",
      text: (
        <>
          {index.failed} document{index.failed === 1 ? "" : "s"} could not be indexed.{" "}
          <Link href="/settings" className="text-accent hover:underline">
            Retry from Settings
          </Link>
        </>
      ),
    });
  }
  if (status.data && !usingLocal) {
    notices.push({
      tone: "info",
      text: "Answers use a cloud provider: your question and the matching passages are sent to it (you consented in Settings). Embeddings stay local.",
    });
  }
  if (notices.length === 0) return null;
  return (
    <div className="space-y-2">
      {notices.map((n, i) => (
        <div
          key={i}
          className={cn(
            "flex gap-2 rounded-md border p-2.5 text-[13px]",
            n.tone === "warning" ? "border-warning/40 bg-warning-soft/50" : "border-border bg-surface-muted/60 text-muted-foreground",
          )}
        >
          {n.tone === "warning" ? (
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
          ) : (
            <Info className="mt-0.5 size-4 shrink-0" />
          )}
          <p>{n.text}</p>
        </div>
      ))}
    </div>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[85%] rounded-lg bg-surface-muted px-3.5 py-2 text-sm whitespace-pre-wrap">{text}</p>
    </div>
  );
}

function StatusBadge({ message }: { message: ChatMessage }) {
  switch (message.status) {
    case "insufficient_evidence":
      return (
        <Badge tone="warning">
          <CircleHelp className="size-3" /> Insufficient evidence
        </Badge>
      );
    case "refused":
      return <Badge tone="danger">Declined</Badge>;
    case "error":
      return <Badge tone="danger">Error</Badge>;
    default:
      return message.grounded ? (
        <Badge tone="success">
          <BadgeCheck className="size-3" /> Cites {message.cited.length} source{message.cited.length === 1 ? "" : "s"}
        </Badge>
      ) : (
        <Badge tone="danger">
          <ShieldAlert className="size-3" /> Unverified
        </Badge>
      );
  }
}

function AssistantMessage({ message }: { message: ChatMessage }) {
  const [activeSource, setActiveSource] = useState<number | null>(null);
  return (
    <article className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-xs text-subtle-foreground">
        <StatusBadge message={message} />
        {message.model ? <span>{message.model}</span> : null}
        <span>· {formatRelativeTime(message.created_at)}</span>
      </div>
      {message.content ? (
        <AnswerContent content={message.content} sources={message.sources} activeSource={activeSource} onCite={setActiveSource} />
      ) : null}
      {message.notes.length ? (
        <ul className="space-y-0.5">
          {message.notes.map((note) => (
            <li key={note} className="flex gap-1.5 text-xs text-muted-foreground">
              <Info className="mt-0.5 size-3 shrink-0" /> {note}
            </li>
          ))}
        </ul>
      ) : null}
      <SourceList sources={message.sources} cited={message.cited} activeSource={activeSource} onSelect={setActiveSource} />
    </article>
  );
}

function StreamingMessage({ state }: { state: StreamingState }) {
  return (
    <article className="space-y-2">
      <div className="flex items-center gap-2 text-xs text-subtle-foreground">
        <Loader2 className="size-3.5 animate-spin" />
        {state.phase === "retrieving"
          ? "Searching your library…"
          : state.text
            ? "Writing answer…"
            : `Reading ${state.sources.length} passage${state.sources.length === 1 ? "" : "s"}… (local models can take a minute)`}
      </div>
      {state.text ? (
        <AnswerContent content={state.text} sources={state.sources} activeSource={null} onCite={() => {}} />
      ) : null}
      {state.notes.map((note) => (
        <p key={note} className="text-xs text-muted-foreground">
          {note}
        </p>
      ))}
    </article>
  );
}

function RequestError({ error }: { error: Error }) {
  const needsSettings = error instanceof ApiError && (error.status === 409 || error.status === 400);
  return (
    <div role="alert" className="flex gap-2 rounded-md border border-danger/30 bg-danger-soft/60 p-3 text-[13px]">
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger" />
      <p>
        {error.message}{" "}
        {needsSettings ? (
          <Link href="/settings" className="text-accent hover:underline">
            Open Settings
          </Link>
        ) : null}
      </p>
    </div>
  );
}
