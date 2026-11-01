import type { Metadata } from "next";

import { PlannedFeature } from "@/components/layout/planned-feature";

export const metadata: Metadata = { title: "Paper Comparison" };

export default function Page() {
  return <PlannedFeature href="/compare" />;
}
