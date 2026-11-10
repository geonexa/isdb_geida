// Fetch wrapper for the Django API: same origin, session cookie, CSRF header.

export class ApiError extends Error {
  status: number;
  data: Record<string, unknown>;
  constructor(status: number, data: Record<string, unknown>) {
    super(typeof data.error === "string" ? data.error : `Request failed (HTTP ${status}). Try again.`);
    this.status = status;
    this.data = data;
  }
  /** Field errors from a Django form: {field: [messages]}. */
  get fieldErrors(): Record<string, string[]> {
    return (this.data.errors as Record<string, string[]>) ?? {};
  }
}

export function getCookie(name: string): string {
  const m = document.cookie.match(new RegExp("(?:^|;\\s*)" + name + "=([^;]+)"));
  return m ? decodeURIComponent(m[1]) : "";
}

async function ensureCsrf() {
  if (!getCookie("csrftoken")) await fetch("/api/auth/csrf/", { credentials: "same-origin" });
}

type Options = { method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"; body?: unknown };

export async function api<T = Record<string, unknown>>(path: string, opts: Options = {}): Promise<T> {
  const method = opts.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") {
    await ensureCsrf();
    headers["X-CSRFToken"] = getCookie("csrftoken");
  }
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(path, {
    method,
    headers,
    credentials: "same-origin",
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, data as Record<string, unknown>);
  return data as T;
}

/** POST multipart form data (file uploads) to the Django API. */
export async function upload<T = Record<string, unknown>>(path: string, form: FormData): Promise<T> {
  await ensureCsrf();
  const res = await fetch(path, {
    method: "POST",
    headers: { Accept: "application/json", "X-CSRFToken": getCookie("csrftoken") },
    credentials: "same-origin",
    body: form,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, data as Record<string, unknown>);
  return data as T;
}
