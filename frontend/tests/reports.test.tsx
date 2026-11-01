import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ReportMarkdown } from "@/components/reports/reports-view";

describe("ReportMarkdown", () => {
  it("renders comparison tables with line breaks inside cells", () => {
    const markdown = [
      "# Comparison",
      "",
      "| Aspect | Paper A |",
      "|---|---|",
      "| **Findings** | First finding (p. 2).<br>Second finding (p. 3). |",
    ].join("\n");
    const { container } = render(<ReportMarkdown markdown={markdown} />);
    expect(container.querySelector("h1")?.textContent).toBe("Comparison");
    const cell = container.querySelectorAll("td")[1];
    expect(cell.querySelectorAll("br")).toHaveLength(1);
    expect(cell.textContent).toBe("First finding (p. 2).Second finding (p. 3).");
  });

  it("drops images and raw HTML and opens links in a new tab", () => {
    const markdown = "![x](http://evil.test/x.png)\n\n<script>alert(1)</script>\n\n[DOI](https://doi.org/10.1/x)";
    const { container } = render(<ReportMarkdown markdown={markdown} />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    const link = container.querySelector("a");
    expect(link?.getAttribute("target")).toBe("_blank");
    expect(link?.getAttribute("rel")).toContain("noopener");
  });
});
