import { AlertTriangle, type LucideIcon } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

export function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("animate-pulse rounded-md bg-surface-muted", className)} {...props} />;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon: LucideIcon;
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-md border border-dashed border-border px-6 py-8 text-center",
        className,
      )}
    >
      <Icon className="size-5 text-subtle-foreground" aria-hidden />
      <p className="mt-2 text-sm font-medium">{title}</p>
      {description ? (
        <p className="mt-1 max-w-sm text-[13px] text-muted-foreground">{description}</p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
  className,
}: {
  error: unknown;
  onRetry?: () => void;
  className?: string;
}) {
  const offline = error instanceof ApiError && error.isNetworkError;
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-start gap-3 rounded-lg border border-danger/30 bg-danger-soft/60 p-4 sm:flex-row sm:items-center",
        className,
      )}
    >
      <AlertTriangle className="size-4 shrink-0 text-danger" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">
          {offline ? "Backend not reachable" : "Could not load data"}
        </p>
        <p className="mt-0.5 text-[13px] text-muted-foreground">
          {message}
          {offline ? (
            <>
              {" "}
              Start it with{" "}
              <code className="rounded bg-surface px-1 font-mono text-xs">
                uvicorn app.main:app --reload
              </code>{" "}
              in the <code className="font-mono text-xs">backend</code> folder.
            </>
          ) : null}
        </p>
      </div>
      {onRetry ? (
        <Button size="sm" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}
