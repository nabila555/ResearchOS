import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CitationText, copyCitations } from "@/components/knowledge/citations-view";
import { layout } from "@/components/knowledge/graph-view";
import type { FormattedCitation, GraphEdge, GraphNode } from "@/types/api";

const citation: FormattedCitation = {
  document_id: 1,
  number: 1,
  text: "Patel, M. (2024). Sleep & screens. Journal <J>, 33.",
  markdown: "",
  parts: [
    { text: "Patel, M. (2024). Sleep & screens. ", italic: false },
    { text: "Journal <J>", italic: true },
    { text: ", 33.", italic: false },
  ],
  missing: [],
  kind: "article",
};

afterEach(() => vi.unstubAllGlobals());

describe("CitationText", () => {
  it("italicises only the marked parts and renders text safely", () => {
    const { container } = render(<CitationText citation={citation} />);
    expect(container.querySelector("i")?.textContent).toBe("Journal <J>");
    expect(container.textContent).toBe(citation.text);
  });
});

describe("copyCitations", () => {
  it("writes plain text and escaped rich HTML with italics", async () => {
    const write = vi.fn(async () => {});
    vi.stubGlobal("navigator", { clipboard: { write, writeText: vi.fn() } });
    class FakeItem {
      constructor(readonly data: Record<string, Blob>) {}
    }
    vi.stubGlobal("ClipboardItem", FakeItem);
    await copyCitations([citation], true);
    const item = (write.mock.calls[0] as unknown as [FakeItem[]])[0][0];
    expect(await item.data["text/plain"].text()).toBe("[1] " + citation.text);
    const html = await item.data["text/html"].text();
    expect(html).toContain("<i>Journal &lt;J&gt;</i>");
    expect(html).toContain("Sleep &amp; screens");
  });

  it("falls back to plain text when rich clipboard is unavailable", async () => {
    const writeText = vi.fn(async () => {});
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    vi.stubGlobal("ClipboardItem", undefined);
    await copyCitations([citation], false);
    expect(writeText).toHaveBeenCalledWith(citation.text);
  });
});

describe("graph layout", () => {
  it("places every node at a finite, distinct position", () => {
    const nodes: GraphNode[] = ["paper:1", "paper:2", "author:1", "topic:1"].map((id) => ({
      id,
      type: id.split(":")[0] as GraphNode["type"],
      label: id,
      data: { degree: 1 },
    }));
    const edges: GraphEdge[] = [
      { id: "a", source: "author:1", target: "paper:1", type: "authored", weight: 1, label: null },
      { id: "b", source: "paper:1", target: "paper:2", type: "similar", weight: 0.8, label: null },
      { id: "c", source: "paper:1", target: "missing:9", type: "tagged", weight: 1, label: null },
    ];
    const positions = layout(nodes, edges);
    expect(positions.size).toBe(4);
    const points = [...positions.values()];
    expect(points.every((p) => Number.isFinite(p.x) && Number.isFinite(p.y))).toBe(true);
    expect(new Set(points.map((p) => `${Math.round(p.x)},${Math.round(p.y)}`)).size).toBe(4);
  });
});
