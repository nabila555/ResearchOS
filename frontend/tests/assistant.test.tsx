import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AnswerContent, expandCitation, linkCitations } from "@/components/assistant/answer-content";
import { ApiError, apiStreamNdjson } from "@/lib/api";
import type { SourcePassage } from "@/types/api";

const source = (n: number): SourcePassage => ({
  n,
  chunk_id: n * 10,
  document_id: n,
  title: `Paper ${n}`,
  authors: [],
  year: null,
  page_start: n,
  page_end: n,
  section: null,
  text: "passage",
  score: 1,
  semantic_similarity: 0.8,
});

describe("citation helpers", () => {
  it("expands lists and ranges", () => {
    expect(expandCitation("2, 3")).toEqual([2, 3]);
    expect(expandCitation("4–6")).toEqual([4, 5, 6]);
    expect(expandCitation("1;3")).toEqual([1, 3]);
  });

  it("turns markers into citation links and leaves other brackets alone", () => {
    expect(linkCitations("A [1]. B [2, 3]. Link [docs](https://x.org)")).toBe(
      "A [1](#cite-1). B [2](#cite-2)[3](#cite-3). Link [docs](https://x.org)",
    );
  });
});

describe("AnswerContent", () => {
  it("renders valid citations as clickable chips and flags unknown ones", async () => {
    const onCite = vi.fn();
    render(
      <AnswerContent
        content="Spindles predict recall [1]. Unsupported claim [9]."
        sources={[source(1)]}
        activeSource={null}
        onCite={onCite}
      />,
    );
    const valid = screen.getByRole("button", { name: "1" });
    expect(valid).toHaveAttribute("title", "Paper 1");
    await userEvent.click(valid);
    expect(onCite).toHaveBeenCalledWith(1);

    const invalid = screen.getByRole("button", { name: "9" });
    expect(invalid.title).toMatch(/not one of the provided sources/i);
    await userEvent.click(invalid);
    expect(onCite).toHaveBeenCalledTimes(1);
  });

  it("does not render raw HTML or images from model output", () => {
    const { container } = render(
      <AnswerContent
        content={"<script>alert(1)</script>\n\n![x](http://evil.test/x.png) **bold**"}
        sources={[]}
        activeSource={null}
        onCite={() => {}}
      />,
    );
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("strong")?.textContent).toBe("bold");
  });
});

function streamResponse(chunks: string[], init: ResponseInit = {}) {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      chunks.forEach((c) => controller.enqueue(encoder.encode(c)));
      controller.close();
    },
  });
  return new Response(body, { status: 200, ...init });
}

afterEach(() => vi.unstubAllGlobals());

describe("apiStreamNdjson", () => {
  it("parses events split across network chunks", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => streamResponse(['{"type":"del', 'ta","text":"Hi"}\n{"type":"done"', "}\n"])),
    );
    const events: unknown[] = [];
    await apiStreamNdjson("/x", {}, (e) => events.push(e));
    expect(events).toEqual([{ type: "delta", text: "Hi" }, { type: "done" }]);
  });

  it("rejects with the server's message when the request is refused", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json({ detail: "Enable this explicitly in Settings first." }, { status: 409 })),
    );
    const error = await apiStreamNdjson("/x", {}, () => {}).catch((e: ApiError) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(409);
    expect((error as ApiError).message).toMatch(/Settings/);
  });
});
