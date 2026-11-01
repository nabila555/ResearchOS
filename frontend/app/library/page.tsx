import type { Metadata } from "next";
import { Suspense } from "react";

import { LibraryView } from "@/components/library/library-view";

export const metadata: Metadata = { title: "Research Library" };

export default function LibraryPage() {
  // LibraryView reads its filters from the URL (useSearchParams), which needs a Suspense boundary.
  return (
    <Suspense>
      <LibraryView />
    </Suspense>
  );
}
