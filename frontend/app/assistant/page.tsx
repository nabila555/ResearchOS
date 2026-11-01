import type { Metadata } from "next";
import { Suspense } from "react";

import { AssistantView } from "@/components/assistant/assistant-view";

export const metadata: Metadata = { title: "AI Assistant" };

export default function AssistantPage() {
  // The selected chat lives in the URL (?chat=ID), read via useSearchParams.
  return (
    <Suspense>
      <AssistantView />
    </Suspense>
  );
}
