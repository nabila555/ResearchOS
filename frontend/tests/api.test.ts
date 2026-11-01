import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch } from "@/lib/api";

function mockFetch(impl: () => Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(impl));
}

afterEach(() => vi.unstubAllGlobals());

/** Await a promise that is expected to reject with an ApiError. */
async function failure(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (error) {
    return error as ApiError;
  }
  throw new Error("Expected the request to fail");
}

describe("apiFetch", () => {
  it("returns parsed JSON on success", async () => {
    mockFetch(async () => Response.json({ status: "ok" }));
    await expect(apiFetch("/api/health")).resolves.toEqual({ status: "ok" });
  });

  it("returns undefined for 204 responses", async () => {
    mockFetch(async () => new Response(null, { status: 204 }));
    await expect(apiFetch("/api/projects/1", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("surfaces FastAPI error detail strings", async () => {
    mockFetch(async () => Response.json({ detail: "Project 9 not found" }, { status: 404 }));
    const error = await failure(apiFetch("/api/projects/9"));
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(404);
    expect(error.message).toBe("Project 9 not found");
  });

  it("joins FastAPI validation messages", async () => {
    mockFetch(async () =>
      Response.json(
        { detail: [{ loc: ["body", "name"], msg: "String should have at least 1 character" }] },
        { status: 422 },
      ),
    );
    const error = await failure(apiFetch("/api/projects", { method: "POST", body: "{}" }));
    expect(error.message).toBe("String should have at least 1 character");
  });

  it("flags network failures", async () => {
    mockFetch(async () => {
      throw new TypeError("Failed to fetch");
    });
    const error = await failure(apiFetch("/api/health"));
    expect(error).toBeInstanceOf(ApiError);
    expect(error.isNetworkError).toBe(true);
  });
});
