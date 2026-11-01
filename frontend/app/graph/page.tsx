import type { Metadata } from "next";

import { GraphView } from "@/components/knowledge/graph-view";

export const metadata: Metadata = { title: "Knowledge Graph" };

export default function GraphPage() {
  return <GraphView />;
}
