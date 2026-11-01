"use client";

import "@xyflow/react/dist/style.css";

import { useQuery } from "@tanstack/react-query";
import {
  Background,
  Controls,
  type Edge,
  Handle,
  MiniMap,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
} from "@xyflow/react";
import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation, type SimulationNodeDatum } from "d3-force";
import { ExternalLink, Network, Search, Sparkles, X } from "lucide-react";
import { useTheme } from "next-themes";
import Link from "next/link";
import { memo, useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/form-controls";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { useCollections } from "@/hooks/use-research-data";
import { cn } from "@/lib/utils";
import { graphService } from "@/services/researchos";
import type { GraphData, GraphEdge, GraphNode, GraphNodeType } from "@/types/api";

export const NODE_STYLES: Record<GraphNodeType, { label: string; color: string }> = {
  paper: { label: "Paper", color: "oklch(0.58 0.16 268)" },
  author: { label: "Author", color: "oklch(0.62 0.13 155)" },
  topic: { label: "Topic (tag)", color: "oklch(0.7 0.14 70)" },
  keyword: { label: "Concept (keyword)", color: "oklch(0.6 0.16 320)" },
  collection: { label: "Collection", color: "oklch(0.6 0.03 265)" },
  method: { label: "Method", color: "oklch(0.6 0.12 220)" },
  finding: { label: "Finding", color: "oklch(0.62 0.16 25)" },
  question: { label: "Research question", color: "oklch(0.62 0.12 290)" },
};

const LAYERS: { key: string; label: string }[] = [
  { key: "author", label: "Authors" },
  { key: "topic", label: "Topics" },
  { key: "keyword", label: "Concepts" },
  { key: "collection", label: "Collections" },
  { key: "similar", label: "Similar papers" },
  { key: "shared_references", label: "Shared references" },
];

const EDGE_STYLE: Record<string, { stroke: string; dash?: string }> = {
  similar: { stroke: "oklch(0.58 0.16 268)", dash: "5 4" },
  shared_references: { stroke: "oklch(0.62 0.16 25)", dash: "2 3" },
};

type FlowData = { node: GraphNode; dimmed: boolean; selected: boolean };

const GraphNodeView = memo(function GraphNodeView({ data }: NodeProps<Node<FlowData>>) {
  const { node, dimmed, selected } = data;
  const style = NODE_STYLES[node.type];
  const isPaper = node.type === "paper";
  const isDetail = node.type === "method" || node.type === "finding" || node.type === "question";
  return (
    <div
      className={cn(
        "rounded-md border bg-surface px-2 py-1 text-foreground shadow-xs transition-opacity",
        isPaper ? "max-w-56 text-[12px] font-medium" : isDetail ? "max-w-64 text-[11px]" : "max-w-40 text-[11px]",
        dimmed && "opacity-25",
        selected && "ring-2 ring-ring",
      )}
      style={{ borderColor: style.color, borderLeftWidth: 4 }}
      title={node.label}
    >
      <Handle type="target" position={Position.Top} className="!size-1 !min-h-0 !min-w-0 !border-0 !bg-transparent" />
      <span className={cn("block", isDetail ? "line-clamp-3" : "truncate")}>{node.label}</span>
      <Handle type="source" position={Position.Bottom} className="!size-1 !min-h-0 !min-w-0 !border-0 !bg-transparent" />
    </div>
  );
});

const nodeTypes = { graph: GraphNodeView };

interface SimNode extends SimulationNodeDatum {
  id: string;
  radius: number;
}

// Rough half-widths of the rendered nodes, so wide detail nodes do not overlap.
const COLLIDE_RADIUS: Partial<Record<GraphNodeType, number>> = { paper: 120, method: 140, finding: 140, question: 140 };

/** Force-directed layout, computed once per graph (synchronously, ~300 ticks). */
export function layout(nodes: GraphNode[], edges: GraphEdge[]): Map<string, { x: number; y: number }> {
  const simNodes: SimNode[] = nodes.map((n, i) => ({
    id: n.id,
    radius: COLLIDE_RADIUS[n.type] ?? 75,
    x: Math.cos(i) * 200 + (i % 7) * 10,
    y: Math.sin(i) * 200 + (i % 5) * 10,
  }));
  const ids = new Set(simNodes.map((n) => n.id));
  const links = edges.filter((e) => ids.has(e.source) && ids.has(e.target)).map((e) => ({ source: e.source, target: e.target, type: e.type }));
  const simulation = forceSimulation(simNodes)
    .force("link", forceLink<SimNode, (typeof links)[number] & { source: string; target: string }>(links).id((d) => d.id).distance((l) => (l.type === "similar" ? 220 : 130)))
    .force("charge", forceManyBody().strength(-420))
    .force("center", forceCenter(0, 0))
    .force("collide", forceCollide<SimNode>((d) => d.radius))
    .stop();
  simulation.tick(300);
  return new Map(simNodes.map((n) => [n.id, { x: n.x ?? 0, y: n.y ?? 0 }]));
}

export function GraphView() {
  const [layers, setLayers] = useState<string[]>(["author", "topic", "keyword", "similar", "shared_references"]);
  const [collectionId, setCollectionId] = useState<number | "">("");
  const [similarity, setSimilarity] = useState(0.75);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [details, setDetails] = useState<Record<number, GraphData>>({});
  const collections = useCollections();
  const { resolvedTheme } = useTheme();

  const graph = useQuery({
    queryKey: ["graph", layers, collectionId, similarity],
    queryFn: () =>
      graphService.get({ include: layers, collection_id: collectionId === "" ? undefined : collectionId, similarity }),
    placeholderData: (previous) => previous,
  });

  const merged = useMemo<GraphData | null>(() => {
    if (!graph.data) return null;
    const nodes = [...graph.data.nodes];
    const edges = [...graph.data.edges];
    for (const extra of Object.values(details)) {
      nodes.push(...extra.nodes);
      edges.push(...extra.edges);
    }
    return { nodes, edges, stats: graph.data.stats };
  }, [graph.data, details]);

  const positions = useMemo(() => (merged ? layout(merged.nodes, merged.edges) : new Map()), [merged]);

  const neighbours = useMemo(() => {
    const map = new Map<string, Set<string>>();
    for (const e of merged?.edges ?? []) {
      if (!map.has(e.source)) map.set(e.source, new Set());
      if (!map.has(e.target)) map.set(e.target, new Set());
      map.get(e.source)!.add(e.target);
      map.get(e.target)!.add(e.source);
    }
    return map;
  }, [merged]);

  const query = search.trim().toLowerCase();
  const focus = selectedId ? new Set([selectedId, ...(neighbours.get(selectedId) ?? [])]) : null;

  const flowNodes: Node<FlowData>[] = (merged?.nodes ?? []).map((node) => ({
    id: node.id,
    type: "graph",
    position: positions.get(node.id) ?? { x: 0, y: 0 },
    data: {
      node,
      selected: node.id === selectedId,
      dimmed: (focus !== null && !focus.has(node.id)) || (query !== "" && !node.label.toLowerCase().includes(query)),
    },
  }));
  const flowEdges: Edge[] = (merged?.edges ?? []).map((edge) => {
    const style = EDGE_STYLE[edge.type];
    const active = !focus || (focus.has(edge.source) && focus.has(edge.target));
    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: selectedId && active ? (edge.label ?? undefined) : undefined,
      style: {
        stroke: style?.stroke ?? "var(--border-strong)",
        strokeDasharray: style?.dash,
        strokeWidth: edge.type === "similar" ? 1 + edge.weight : 1,
        opacity: active ? 0.9 : 0.12,
      },
      labelStyle: { fontSize: 10, fill: "var(--muted-foreground)" },
      labelBgStyle: { fill: "var(--surface)" },
    };
  });

  const selected = merged?.nodes.find((n) => n.id === selectedId) ?? null;

  async function expandPaper(documentId: number) {
    try {
      const data = await graphService.paper(documentId);
      if (!data.has_profile) {
        toast.info("Extract this paper's profile first (on its document page).");
        return;
      }
      if (data.nodes.length === 0) toast.info("The profile has no verified methods, findings or questions.");
      setDetails((d) => ({ ...d, [documentId]: data }));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not load details");
    }
  }

  function toggleLayer(key: string) {
    setLayers((current) => (current.includes(key) ? current.filter((k) => k !== key) : [...current, key]));
  }

  return (
    <div className="flex h-[calc(100dvh-3rem)] flex-col md:h-dvh">
      <header className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2.5">
        <h1 className="mr-2 text-sm font-semibold">Knowledge Graph</h1>
        <div className="flex flex-wrap gap-1">
          {LAYERS.map((layer) => (
            <button
              key={layer.key}
              type="button"
              aria-pressed={layers.includes(layer.key)}
              onClick={() => toggleLayer(layer.key)}
              className={cn(
                "h-7 rounded-md border px-2 text-xs transition-colors",
                layers.includes(layer.key) ? "border-accent bg-accent-soft text-accent-soft-foreground" : "border-border text-muted-foreground",
              )}
            >
              {layer.label}
            </button>
          ))}
        </div>
        <Select aria-label="Scope" value={collectionId} onChange={(e) => setCollectionId(e.target.value ? Number(e.target.value) : "")} className="h-7 w-auto text-xs">
          <option value="">Whole library</option>
          {collections.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
        {layers.includes("similar") ? (
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
            Similarity ≥ {similarity.toFixed(2)}
            <input type="range" min={0.5} max={0.95} step={0.05} value={similarity} onChange={(e) => setSimilarity(Number(e.target.value))} className="w-24 accent-[var(--accent)]" />
          </label>
        ) : null}
        <div className="relative ml-auto w-48">
          <Search className="pointer-events-none absolute top-1/2 left-2 size-3.5 -translate-y-1/2 text-subtle-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Highlight…" className="h-7 pl-7 text-xs" aria-label="Highlight nodes" />
        </div>
      </header>

      <div className="relative flex min-h-0 flex-1">
        {graph.isError ? (
          <div className="p-6">
            <ErrorState error={graph.error} onRetry={() => graph.refetch()} />
          </div>
        ) : graph.isPending ? (
          <Skeleton className="m-6 flex-1" />
        ) : !merged || (merged.stats.paper ?? 0) === 0 ? (
          <div className="flex-1 p-6">
            <EmptyState icon={Network} title="Nothing to map yet" description="Import papers into the library; the graph links them by authors, topics, concepts, similarity and shared references." className="py-16" />
          </div>
        ) : (
          <div className="min-w-0 flex-1">
            <ReactFlow
              nodes={flowNodes}
              edges={flowEdges}
              nodeTypes={nodeTypes}
              onNodeClick={(_, node) => setSelectedId(node.id)}
              onPaneClick={() => setSelectedId(null)}
              nodesConnectable={false}
              fitView
              minZoom={0.1}
              colorMode={resolvedTheme === "dark" ? "dark" : "light"}
              proOptions={{ hideAttribution: true }}
            >
              <Background gap={24} size={1} />
              <Controls showInteractive={false} />
              <MiniMap pannable zoomable nodeColor={(n) => NODE_STYLES[(n.data as FlowData).node.type].color} className="!hidden md:!block" />
            </ReactFlow>
            <div className="pointer-events-none absolute bottom-3 left-14 flex flex-wrap gap-2 rounded-md border border-border bg-surface/90 px-2 py-1.5 text-[11px] shadow-xs">
              {Object.entries(merged.stats).map(([type, count]) => (
                <span key={type} className="flex items-center gap-1">
                  <span className="size-2 rounded-full" style={{ background: NODE_STYLES[type as GraphNodeType].color }} />
                  {NODE_STYLES[type as GraphNodeType].label} {count}
                </span>
              ))}
            </div>
          </div>
        )}

        {selected ? (
          <aside className="absolute inset-y-0 right-0 z-10 w-80 overflow-y-auto border-l border-border bg-surface p-4 shadow-xl">
            <div className="flex items-start justify-between gap-2">
              <Badge>{NODE_STYLES[selected.type].label}</Badge>
              <button type="button" onClick={() => setSelectedId(null)} className="rounded p-1 text-subtle-foreground hover:text-foreground" aria-label="Close details">
                <X className="size-4" />
              </button>
            </div>
            <h2 className="mt-2 text-sm font-semibold leading-snug">{selected.label}</h2>
            {selected.data.quote ? (
              <p className="mt-2 text-xs text-muted-foreground italic">
                “{selected.data.quote}”{selected.data.page ? ` (p. ${selected.data.page})` : ""}
              </p>
            ) : null}
            {selected.data.document_id ? (
              <div className="mt-3 flex flex-wrap gap-2">
                <Button asChild size="sm">
                  <Link href={`/library/${selected.data.document_id}${selected.data.page ? `?page=${selected.data.page}` : ""}`}>
                    <ExternalLink /> Open {selected.type === "paper" ? "paper" : "source"}
                  </Link>
                </Button>
                {selected.type === "paper" && !details[selected.data.document_id] ? (
                  <Button size="sm" variant="ghost" onClick={() => expandPaper(selected.data.document_id!)}>
                    <Sparkles /> Methods & findings
                  </Button>
                ) : null}
              </div>
            ) : null}
            <p className="mt-4 mb-1.5 text-xs font-medium text-muted-foreground">Connected ({neighbours.get(selected.id)?.size ?? 0})</p>
            <ul className="space-y-1">
              {[...(neighbours.get(selected.id) ?? [])].map((id) => {
                const node = merged?.nodes.find((n) => n.id === id);
                const edge = merged?.edges.find((e) => (e.source === id && e.target === selected.id) || (e.target === id && e.source === selected.id));
                if (!node) return null;
                return (
                  <li key={id}>
                    <button type="button" onClick={() => setSelectedId(id)} className="flex w-full items-start gap-2 rounded px-1.5 py-1 text-left text-[13px] hover:bg-surface-muted">
                      <span className="mt-1.5 size-2 shrink-0 rounded-full" style={{ background: NODE_STYLES[node.type].color }} />
                      <span className="min-w-0">
                        <span className="line-clamp-2">{node.label}</span>
                        {edge?.label ? <span className="text-[11px] text-subtle-foreground">{edge.label}</span> : null}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </aside>
        ) : null}
      </div>
    </div>
  );
}
