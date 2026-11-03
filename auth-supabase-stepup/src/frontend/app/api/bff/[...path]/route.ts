import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { COOKIE } from "@/lib/config";
import { bad, csrfOk } from "@/lib/route-helpers";
import { sessionToken } from "@/lib/supabase/server";

const ALLOWED = /^v1\/[a-z0-9\-_/]+$/i;                       // only the authenticated API; public/admin-only prefixes are never proxied
const cookie = (req: Request, n: string) => req.headers.get("cookie")?.match(new RegExp(`(?:^|; )${n}=([^;]+)`))?.[1];

async function forward(req: Request, path: string, at: string | null) {
  const org = cookie(req, COOKIE.org);
  const h = new Headers();
  if (at) h.set("Authorization", `Bearer ${at}`);
  if (org) h.set("X-Org-Id", org);
  const imp = cookie(req, COOKIE.imp);
  if (imp) h.set("X-Impersonation", decodeURIComponent(imp));
  for (const k of ["if-match", "idempotency-key"]) { const v = req.headers.get(k); if (v) h.set(k, v); }
  const ct = req.headers.get("content-type");
  if (ct) h.set("content-type", ct);
  const url = new URL(req.url);
  const body = ["GET", "HEAD"].includes(req.method) ? undefined : await req.arrayBuffer();
  return backendFetch(`/${path}${url.search}`, { method: req.method, headers: h, body, incoming: req.headers });
}

async function handle(req: Request, ctx: { params: Promise<{ path: string[] }> }) {
  const path = (await ctx.params).path.join("/");
  if (!ALLOWED.test(path) || path.includes("..")) return bad(404, "not_found");
  if (!["GET", "HEAD"].includes(req.method) && !csrfOk(req)) return bad(403, "csrf");
  const r = await forward(req.clone(), path, await sessionToken(req));      // the proxy already refreshed the session before this handler ran
  const out = new NextResponse(r.body, { status: r.status });
  for (const k of ["content-type", "content-disposition", "cache-control", "retry-after", "etag", "x-ai-status", "server-timing"]) { const v = r.headers.get(k); if (v) out.headers.set(k, v); }
  return out;
}

export { handle as GET, handle as POST, handle as PUT, handle as PATCH, handle as DELETE };
