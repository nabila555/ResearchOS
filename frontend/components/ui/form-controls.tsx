import * as React from "react";

import { cn } from "@/lib/utils";

const fieldClasses =
  "w-full rounded-md border border-border bg-surface px-2.5 text-sm text-foreground shadow-xs outline-none transition-colors placeholder:text-subtle-foreground focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50";

export function Input({ className, ...props }: React.ComponentProps<"input">) {
  return <input className={cn(fieldClasses, "h-8", className)} {...props} />;
}

export function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return <textarea className={cn(fieldClasses, "min-h-20 py-2 leading-relaxed", className)} {...props} />;
}

export function Select({ className, ...props }: React.ComponentProps<"select">) {
  return <select className={cn(fieldClasses, "h-8 pr-7", className)} {...props} />;
}

export function Label({ className, ...props }: React.ComponentProps<"label">) {
  return (
    <label
      className={cn("mb-1.5 block text-[13px] font-medium text-foreground", className)}
      {...props}
    />
  );
}
