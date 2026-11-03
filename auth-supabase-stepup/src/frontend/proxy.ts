import { NextResponse, type NextRequest } from "next/server";
import { backendFetch } from "./lib/backend";
import { embedOrigins } from "./lib/embed";
import { appCsp } from "./lib/csp";
import { perfEnabled } from "./lib/perf-env";
import { COOKIE } from "./lib/config";
import { mustChallenge } from "./lib/two-step";
import { updateSession } from "./lib/supabase/middleware";

/** The public website (app/(site)): anyone may read it, signed in or not. `/security` is the signed-in organisation page, so the trust page lives at `/trust`. */
const SITE = /^\/(solutions|pricing|industries|how-we-measure|trust|about|insights|innovation-lab|contact|privacy|terms|site|sitemap\.xml|robots\.txt)(\/|$)/;      // `/site/*` are the website's pictures (public/site)
const PUBLIC = [/^\/$/, SITE, /^\/auth(\/|$)/, /^\/design/, /^\/runner/, /^\/interview-participant/, /^\/s\//, /^\/i\//, /^\/api\/site\//, /^\/kiosk-app/, /^\/kiosk-sw\.js$/, /^\/api\/kiosk\//, /^\/_next\//, /^\/favicon/, /^\/api\/public\//, /^\/site-home/, /^\/shared\//, /^\/embed\//, /^\/embed\.js$/, /^\/api\/shared\//];

/** Mockup and preview pages exist for development and the generator's tests only. In a production build the bare preview routes answer 404 (the real `/s/[token]`, `/i/[token]` and
 *  `/interview-participant/[token]` are untouched) and `/site-home`, replaced by the new `/`, is moved there. */
const PREVIEW = /^\/(runner|interview-participant|design-system|design)\/?$/;
const SUPERSEDED = /^\/site-home(\/|$)/;

/** Framing policy for public pages. CSP frame-ancestors is authoritative; X-Frame-Options is the legacy twin and is only sent when it says the same thing
 *  (an allow-list of origins cannot be expressed in X-Frame-Options, so it is omitted there and the CSP decides). */
function framing(res: NextResponse, ancestors: string[]) {
  res.headers.set("Content-Security-Policy", `frame-ancestors ${ancestors.length ? ancestors.join(" ") : "'none'"}`);
  if (!ancestors.length) res.headers.set("X-Frame-Options", "DENY");
  else if (ancestors.length === 1 && ancestors[0] === "'self'") res.headers.set("X-Frame-Options", "SAMEORIGIN");
  res.headers.set("Referrer-Policy", "no-referrer");
  return res;
}

/** Gate: signed-out visitors go to /auth; the Supabase session is refreshed here (the only place cookies can be rewritten for page requests); every page gets a per-request CSP nonce. */
export async function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (process.env.NODE_ENV === "production") {
    if (SUPERSEDED.test(pathname)) return NextResponse.redirect(new URL("/", req.url), 301);
    if (PREVIEW.test(pathname)) return NextResponse.rewrite(new URL("/__not-found", req.url), { status: 404 });
  }
  const embed = /^\/embed\/([A-Za-z0-9_-]{20,100})$/.exec(pathname);
  if (embed) {                                                     // only the origins the share owner listed may frame the embed; unknown/revoked tokens may not be framed at all
    const meta = await backendFetch(`/public/v1/embed/${embed[1]}/meta`, { incoming: req.headers }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    return framing(NextResponse.next(), (meta?.allowed_origins as string[] | undefined) ?? []);
  }
  if (/^\/shared\//.test(pathname)) return framing(NextResponse.next(), []);                      // a share link is a page of its own, never a frame
  // The respondent runner. By default only our own origin may frame it (a foreign page wrapping the consent screen = clickjacking). `?embed=1` pages may also be framed
  // by the exact https origins the author listed for that collector; an unknown/revoked token may not be framed by anyone but us. Every /s/* response gets the header, errors included.
  const runner = /^\/s\/([A-Za-z0-9_-]{8,128})\/?$/.exec(pathname);
  if (runner && req.nextUrl.searchParams.get("embed") === "1") {
    const origins = await embedOrigins(runner[1], req.headers);
    return framing(NextResponse.next(), origins === null ? [] : ["'self'", ...origins]);
  }
  if (/^\/s(\/|$)/.test(pathname)) return framing(NextResponse.next(), ["'self'"]);
  if (PUBLIC.some((p) => p.test(pathname)) && !/^\/auth(\/|$)/.test(pathname)) return NextResponse.next();       // anonymous surfaces keep their own framing rules
  const nonce = btoa(crypto.randomUUID());
  const csp = appCsp(nonce);
  const fwd = new Headers(req.headers);
  if (perfEnabled()) fwd.set("x-pathname", pathname);                      // route name for the PERF_LOG line
  fwd.set("x-nonce", nonce); fwd.set("content-security-policy", csp);        // Next.js stamps its own inline scripts with this nonce
  const sess = await updateSession(req, fwd);                                // refreshes the Supabase session cookies when the access token is near expiry
  const done = (res: NextResponse) => { res.headers.set("Content-Security-Policy", csp); return res; };
  if (/^\/auth(\/|$)/.test(pathname)) return done(sess.response());
  if (!sess.signedIn) {
    if (pathname.startsWith("/api/")) return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
    const u = req.nextUrl.clone(); u.pathname = "/auth"; u.search = `?next=${encodeURIComponent(pathname)}`;
    return NextResponse.redirect(u);
  }
  if (sess.aal !== "aal2" && !pathname.startsWith("/api/") && mustChallenge(req.cookies.get(COOKIE.role)?.value, req.cookies.get("sv_mfa")?.value)) {
    const u = req.nextUrl.clone(); u.pathname = "/auth"; u.search = `?mfa=1&next=${encodeURIComponent(pathname)}`;      // the API would refuse this page's data anyway: go straight to the second step
    return done(NextResponse.redirect(u));
  }
  return done(sess.response());
}

export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"] };
