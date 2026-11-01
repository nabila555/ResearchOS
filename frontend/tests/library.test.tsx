import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import {
  HighlightedSnippet,
  formatAuthors,
  formatBytes,
  formatPages,
} from "@/components/library/shared";
import { TagInput } from "@/components/ui/tag-input";
import { toQueryString } from "@/lib/api";

describe("HighlightedSnippet", () => {
  it("marks highlighted terms and renders everything as text", () => {
    const { container } = render(
      <HighlightedSnippet text={"before \u0002spindle\u0003 and <b>tags</b> \u0002density\u0003"} />,
    );
    expect([...container.querySelectorAll("mark")].map((m) => m.textContent)).toEqual([
      "spindle",
      "density",
    ]);
    // Markup inside a snippet is shown literally, never interpreted.
    expect(container.querySelector("b")).toBeNull();
    expect(container.textContent).toBe("before spindle and <b>tags</b> density");
  });

  it("drops unbalanced markers", () => {
    const { container } = render(<HighlightedSnippet text={"stray \u0003 marker \u0002"} />);
    expect(container.textContent).toBe("stray  marker ");
  });
});

describe("formatters", () => {
  it("formats author lists", () => {
    expect(formatAuthors([])).toBe("");
    expect(formatAuthors(["A", "B"])).toBe("A, B");
    expect(formatAuthors(["A", "B", "C", "D"])).toBe("A, B, C et al.");
  });

  it("formats page ranges", () => {
    expect(formatPages(null, null)).toBeNull();
    expect(formatPages(3, 3)).toBe("p. 3");
    expect(formatPages(3, 5)).toBe("pp. 3–5");
  });

  it("formats byte sizes", () => {
    expect(formatBytes(null)).toBe("—");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(4096)).toBe("4 KB");
    expect(formatBytes(3 * 1024 * 1024)).toBe("3.0 MB");
  });
});

describe("toQueryString", () => {
  it("skips empty values and repeats arrays", () => {
    expect(toQueryString({ q: "sleep memory", doc_type: ["pdf", "note"], tag: "", year_from: undefined, offset: 0 })).toBe(
      "?q=sleep+memory&doc_type=pdf&doc_type=note&offset=0",
    );
    expect(toQueryString({})).toBe("");
  });
});

function ControlledTagInput({ initial = [] as string[] }) {
  const [tags, setTags] = useState(initial);
  return (
    <>
      <TagInput value={tags} onChange={setTags} />
      <output data-testid="tags">{tags.join("|")}</output>
    </>
  );
}

describe("TagInput", () => {
  it("adds on Enter and comma, ignores case-insensitive duplicates, removes with Backspace", async () => {
    const user = userEvent.setup();
    render(<ControlledTagInput initial={["Sleep"]} />);
    const input = screen.getByRole("textbox");

    await user.type(input, "memory{Enter}");
    await user.type(input, "#EEG,");
    await user.type(input, "sleep{Enter}");
    expect(screen.getByTestId("tags")).toHaveTextContent("Sleep|memory|EEG");

    await user.type(input, "{Backspace}");
    expect(screen.getByTestId("tags")).toHaveTextContent("Sleep|memory");

    await user.click(screen.getByRole("button", { name: "Remove tag Sleep" }));
    expect(screen.getByTestId("tags")).toHaveTextContent(/^memory$/);
  });
});
