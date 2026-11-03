import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { SUPABASE_PUBLISHABLE_KEY, SUPABASE_URL } from "./env";

/** Refreshes the Supabase session cookies when the access token is near expiry (getClaims does it) and reports whether a verified user is signed in.
 *  Returns the response that carries the refreshed cookies; the caller must return that same response (or copy its cookies and cache headers). */
export async function updateSession(req: NextRequest, headers?: Headers) {
  let response = NextResponse.next({ request: headers ? { headers } : req });
  const sb = createServerClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
    cookies: {
      getAll: () => req.cookies.getAll(),
      setAll(list, cacheHeaders) {
        for (const c of list) req.cookies.set(c.name, c.value);
        if (headers) headers.set("cookie", req.cookies.toString());          // server components must see the refreshed session too
        response = NextResponse.next({ request: headers ? { headers } : req });
        for (const c of list) response.cookies.set(c.name, c.value, c.options);
        for (const [k, v] of Object.entries(cacheHeaders ?? {})) response.headers.set(k, v);
      },
    },
  });
  const { data } = await sb.auth.getClaims();
  const aal = (data?.claims as { aal?: string } | undefined)?.aal;
  return { response: () => response, signedIn: !!data?.claims, aal: aal === "aal2" ? "aal2" : "aal1" };
}
