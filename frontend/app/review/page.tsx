import type { Metadata } from "next";
import { Suspense } from "react";

import { ReviewView } from "@/components/knowledge/review-view";

export const metadata: Metadata = { title: "Literature Review" };

export default function ReviewPage() {
  // The open review lives in the URL (?id=N), read with useSearchParams.
  return (
    <Suspense>
      <ReviewView />
    </Suspense>
  );
}
