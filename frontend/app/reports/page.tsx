import type { Metadata } from "next";
import { Suspense } from "react";

import { ReportsView } from "@/components/reports/reports-view";

export const metadata: Metadata = { title: "Reports" };

export default function ReportsPage() {
  // The open report lives in the URL (?id=N), read with useSearchParams.
  return (
    <Suspense>
      <ReportsView />
    </Suspense>
  );
}
