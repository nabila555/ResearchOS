import type { Metadata } from "next";
import { Suspense } from "react";

import { CompareView } from "@/components/analysis/compare-view";

export const metadata: Metadata = { title: "Paper Comparison" };

export default function Page() {
  // The selected run lives in the URL (?id=N), read with useSearchParams.
  return (
    <Suspense>
      <CompareView />
    </Suspense>
  );
}
