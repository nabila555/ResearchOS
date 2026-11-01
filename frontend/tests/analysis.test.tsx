import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EvidenceChip, FieldStatements } from "@/components/analysis/shared";
import type { Evidence } from "@/types/api";

const verified: Evidence = {
  chunk_id: 1,
  page_start: 3,
  page_end: 3,
  section: "Methods",
  quote: "We recruited 48 healthy adults",
  verified: true,
  reason: null,
};
const unverified: Evidence = { ...verified, verified: false, reason: "number 52 does not appear in the cited excerpt" };

describe("EvidenceChip", () => {
  it("links verified evidence to the cited page and shows the quote on hover", () => {
    render(<EvidenceChip documentId={7} evidence={verified} />);
    const link = screen.getByRole("link", { name: "p. 3" });
    expect(link).toHaveAttribute("href", "/library/7?page=3");
    expect(link).toHaveAttribute("title", "“We recruited 48 healthy adults”");
  });

  it("marks unverified evidence and explains why, without a link", () => {
    render(<EvidenceChip documentId={7} evidence={unverified} />);
    expect(screen.queryByRole("link")).toBeNull();
    const chip = screen.getByText("unverified");
    expect(chip.closest("span")?.getAttribute("title")).toMatch(/number 52/);
  });
});

describe("FieldStatements", () => {
  it("shows Not reported for empty fields", () => {
    render(<FieldStatements documentId={1} value={{ status: "not_reported", statements: [] }} />);
    expect(screen.getByText("Not reported")).toBeInTheDocument();
  });

  it("renders several statements as a list with their evidence", () => {
    render(
      <FieldStatements
        documentId={1}
        value={{
          status: "partial",
          statements: [
            { text: "Finding A", evidence: verified },
            { text: "Finding B", evidence: unverified },
          ],
        }}
      />,
    );
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "p. 3" })).toBeInTheDocument();
    expect(screen.getByText("unverified")).toBeInTheDocument();
  });
});
