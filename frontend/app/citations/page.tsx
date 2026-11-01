import type { Metadata } from "next";

import { CitationsView } from "@/components/knowledge/citations-view";

export const metadata: Metadata = { title: "Citation Manager" };

export default function CitationsPage() {
  return <CitationsView />;
}
