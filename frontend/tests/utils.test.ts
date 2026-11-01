import { describe, expect, it } from "vitest";

import { formatRelativeTime, pluralize } from "@/lib/utils";

describe("pluralize", () => {
  it("uses singular for one", () => {
    expect(pluralize(1, "source")).toBe("1 source");
  });
  it("uses plural otherwise", () => {
    expect(pluralize(0, "source")).toBe("0 sources");
    expect(pluralize(1200, "paper")).toBe("1,200 papers");
  });
  it("supports irregular plurals", () => {
    expect(pluralize(2, "analysis", "analyses")).toBe("2 analyses");
  });
});

describe("formatRelativeTime", () => {
  const now = new Date("2026-01-10T12:00:00Z");

  it("reports very recent times as just now", () => {
    expect(formatRelativeTime("2026-01-10T11:59:40Z", now)).toBe("just now");
  });
  it("formats minutes, hours and days", () => {
    expect(formatRelativeTime("2026-01-10T11:55:00Z", now)).toBe("5 minutes ago");
    expect(formatRelativeTime("2026-01-10T09:00:00Z", now)).toBe("3 hours ago");
    expect(formatRelativeTime("2026-01-09T12:00:00Z", now)).toBe("yesterday");
  });
});
