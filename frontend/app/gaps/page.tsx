import type { Metadata } from "next";
import { Suspense } from "react";

import { GapsView } from "@/components/analysis/gaps-view";

export const metadata: Metadata = { title: "Research Gap Finder" };

export default function Page() {
  // The selected run lives in the URL (?id=N), read with useSearchParams.
  return (
    <Suspense>
      <GapsView />
    </Suspense>
  );
}
