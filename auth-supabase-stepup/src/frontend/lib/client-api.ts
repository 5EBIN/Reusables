"use client";

/** The API answers with the fallback and `X-AI-Status: unavailable` when the model provider could not be used. */
export const AI_UNAVAILABLE = "sv:ai-unavailable";

export type Result<T> = { ok: true; status: number; data: T; headers?: Headers } | { ok: false; status: number; error: string; data?: any };

/** Browser -> BFF. Always same-origin with the CSRF header; tokens live in HttpOnly cookies the page cannot read. */
export async function call<T = any>(path: string, method: string, body?: unknown, headers?: Record<string, string>): Promise<Result<T>> {
  try {
    const r = await fetch(path, { method, headers: { "content-type": "application/json", "x-sv-csrf": "1", ...headers }, body: body === undefined ? undefined : (typeof body === "string" || body instanceof Blob || body instanceof ArrayBuffer ? (body as BodyInit) : JSON.stringify(body)), credentials: "same-origin" });
    if (r.headers.get("x-ai-status") === "unavailable") window.dispatchEvent(new Event(AI_UNAVAILABLE));       // the result is the fallback: say so (components/AiNotice.tsx)
    const ct = r.headers.get("content-type") ?? "";
    const data = ct.includes("json") ? await r.json().catch(() => null) : null;
    if (r.ok) return { ok: true, status: r.status, data: data as T, headers: r.headers };
    return { ok: false, status: r.status, error: (data && (data.error ?? data.detail)) || `http_${r.status}`, data };
  } catch {
    return { ok: false, status: 0, error: "network" };
  }
}
export const post = <T = any>(path: string, body?: unknown) => call<T>(path, "POST", body);
export const get = <T = any>(path: string) => call<T>(path, "GET");
export const put = <T = any>(path: string, body?: unknown, headers?: Record<string, string>) => call<T>(path, "PUT", body, headers);
export const del = <T = any>(path: string) => call<T>(path, "DELETE");
/** Anonymous respondent API (collector / invitation / interview links). */
export const pub = (p: string) => `/api/public/${p.replace(/^\//, "")}`;
export const bff = (p: string) => `/api/bff/${p.replace(/^\//, "")}`;
