/**
 * Minimal typed fetch client for the ResearchOS FastAPI backend.
 * All requests go to the local backend; nothing is sent to third parties.
 */

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
    readonly detail?: unknown,
    /** Full JSON error body, e.g. { detail, existing_document_id }. */
    readonly body?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** True when the backend could not be reached at all. */
  get isNetworkError() {
    return this.status === null;
  }
}

function messageFromDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  // FastAPI validation errors: [{ loc, msg, type }, ...]
  if (Array.isArray(detail) && detail.length > 0 && typeof detail[0]?.msg === "string") {
    return detail.map((d: { msg: string }) => d.msg).join("; ");
  }
  return fallback;
}

function errorFromBody(status: number, body: unknown): ApiError {
  const record = body && typeof body === "object" ? (body as Record<string, unknown>) : undefined;
  return new ApiError(
    messageFromDetail(record?.detail, `Request failed with status ${status}`),
    status,
    record?.detail,
    record,
  );
}

const networkError = () =>
  new ApiError(`Cannot reach the ResearchOS backend at ${API_BASE_URL}. Is it running?`, null);

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        ...(init.body && !(init.body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {}),
        ...init.headers,
      },
    });
  } catch {
    throw networkError();
  }

  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = undefined;
    }
    throw errorFromBody(response.status, body);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** POST multipart data with upload progress (fetch cannot report upload progress). */
export function apiUpload<T>(
  path: string,
  form: FormData,
  onProgress?: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}${path}`);
    xhr.responseType = "json";
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(event.loaded / event.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(xhr.response as T);
      else reject(errorFromBody(xhr.status, xhr.response));
    };
    xhr.onerror = () => reject(networkError());
    xhr.onabort = () => reject(new ApiError("Upload cancelled", 0));
    signal?.addEventListener("abort", () => xhr.abort());
    xhr.send(form);
  });
}

/** Serialise a filter object into a query string, repeating array values. */
export function toQueryString(params: object): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => search.append(key, String(v)));
    else search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}
