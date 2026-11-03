import * as nextHeaders from "next/headers";
import { redirect } from "next/navigation";
import { backendHeaders } from "./backend";
import { BACKEND_URL, COOKIE } from "./config";
import { trackCall } from "./perf";
import { serverToken } from "./supabase/server";

/** The browser's request headers, for the client address and User-Agent. Absent outside a request (and in unit tests that mock only cookies). */
async function incomingHeaders(): Promise<Headers | null> {
  try { return typeof nextHeaders.headers === "function" ? await nextHeaders.headers() : null; } catch { return null; }
}

export class ApiError extends Error {
  constructor(public status: number, public body: unknown) { super(`API ${status}`); }
}

/** Server-side call to the backend as the signed-in user. Never exposes tokens to the browser. */
export async function api<T = unknown>(path: string, init: RequestInit & { org?: boolean } = {}): Promise<T> {
  const jar = await nextHeaders.cookies();
  const at = await serverToken(jar);
  const org = jar.get(COOKIE.org)?.value;
  const headers = backendHeaders(await incomingHeaders(), init.headers);
  if (at) headers.set("Authorization", `Bearer ${at}`);
  if (org && init.org !== false) headers.set("X-Org-Id", org);
  const imp = jar.get(COOKIE.imp)?.value;                 // support session (staff): read-only, sent as X-Impersonation
  if (imp && init.org !== false) headers.set("X-Impersonation", imp);
  if (init.body && !headers.has("content-type")) headers.set("content-type", "application/json");
  const done = trackCall(path);
  let r: Response | undefined;
  try {
    r = await fetch(`${BACKEND_URL}${path}`, { ...init, headers, cache: "no-store" });
  } finally {
    done(r?.status ?? 0, r?.headers.get("server-timing"));
  }
  const text = await r.text();
  const body = text ? safeJson(text) : null;
  if (r.status === 403 && (body as { detail?: { code?: string } } | null)?.detail?.code === "mfa_required") redirect("/auth?mfa=1");       // sign-in asks for (or sets up) the second step
  if (!r.ok) throw new ApiError(r.status, body);
  return body as T;
}

const safeJson = (s: string) => { try { return JSON.parse(s); } catch { return s; } };
