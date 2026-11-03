import { createServerClient, parseCookieHeader } from "@supabase/ssr";
import { cookies } from "next/headers";
import { SUPABASE_PUBLISHABLE_KEY, SUPABASE_URL } from "./env";

type Jar = { name: string; value: string }[];

/** Server client for server components and route handlers (Next.js cookie store). Writes are ignored where Next.js forbids them (server components);
 *  the proxy refreshes the session before any page renders. */
export async function createClient() {
  const jar = await cookies();
  return createServerClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
    cookies: {
      getAll: () => jar.getAll(),
      setAll(list) { try { for (const c of list) jar.set(c.name, c.value, c.options); } catch { /* server component */ } },
    },
  });
}

/** The user's access token for a call to the backend, or null. The session is verified first (`getClaims` checks the signature against the project's keys,
 *  never trusting the cookie alone); the token itself is then read from the same session. FastAPI verifies it again. */
export async function tokenFromCookies(all: () => Jar): Promise<string | null> {
  const sb = createServerClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, { cookies: { getAll: all, setAll() { /* the proxy owns refreshes */ } } });
  const { data } = await sb.auth.getClaims();
  if (!data?.claims) return null;
  const { data: s } = await sb.auth.getSession();
  return s.session?.access_token ?? null;
}

/** Same, for a route handler that received a plain Request. */
export const sessionToken = (req: Request) => tokenFromCookies(() => parseCookieHeader(req.headers.get("cookie") ?? "").map((c) => ({ name: c.name, value: c.value ?? "" })));

/** Same, for server components (Next.js cookie store). */
export async function serverToken(jar: Awaited<ReturnType<typeof cookies>>) {
  return tokenFromCookies(() => jar.getAll());
}
