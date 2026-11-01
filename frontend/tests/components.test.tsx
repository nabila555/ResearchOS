import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Library } from "lucide-react";
import { describe, expect, it, vi } from "vitest";

import { NAV_ITEMS, isAvailable } from "@/components/layout/navigation";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { ApiError } from "@/lib/api";

describe("EmptyState", () => {
  it("renders title, description and action", () => {
    render(
      <EmptyState
        icon={Library}
        title="Nothing here"
        description="Add something"
        action={<button>Add</button>}
      />,
    );
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.getByText("Add something")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add" })).toBeInTheDocument();
  });
});

describe("ErrorState", () => {
  it("explains how to start the backend when it is offline", () => {
    render(<ErrorState error={new ApiError("Cannot reach backend", null)} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Backend not reachable");
    expect(screen.getByText(/uvicorn app\.main:app/)).toBeInTheDocument();
  });

  it("calls onRetry", async () => {
    const onRetry = vi.fn();
    render(<ErrorState error={new ApiError("Boom", 500)} onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Could not load data");
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});

describe("navigation", () => {
  it("contains the ten main sections in order", () => {
    expect(NAV_ITEMS.map((i) => i.label)).toEqual([
      "Dashboard",
      "Research Library",
      "AI Assistant",
      "Research Gap Finder",
      "Paper Comparison",
      "Knowledge Graph",
      "Literature Review",
      "Citation Manager",
      "Research Projects",
      "Settings",
    ]);
  });

  it("describes every unbuilt section's plan", () => {
    for (const item of NAV_ITEMS.filter((i) => !isAvailable(i))) {
      expect(item.planned.length).toBeGreaterThan(0);
    }
  });
});
