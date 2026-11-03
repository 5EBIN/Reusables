import { ApiError } from "@/lib/api-server";

/** Resolve to null when the API answers with an error (404 for hidden surfaces, 403 for missing role, 5xx) so a page can degrade instead of crashing. */
export async function soft<T>(p: Promise<T>): Promise<T | null> {
  try { return await p; } catch (e) { if (e instanceof ApiError) return null; throw e; }
}
/** The fallback when the API answers with an error; anything else (above all the redirect to two-step sign-in, which `api()` throws) goes on up. */
export async function orElse<T>(p: Promise<unknown>, fallback: T, pick: (v: never) => T = (v) => v as T): Promise<T> {
  try { return pick((await p) as never); } catch (e) { if (e instanceof ApiError) return fallback; throw e; }
}
/** True when the failure is exactly "this surface does not exist for you" (platform admin for non-staff). */
export async function missing(p: Promise<unknown>): Promise<boolean> {
  try { await p; return false; } catch (e) { if (e instanceof ApiError && e.status === 404) return true; throw e; }
}

/** 1490 -> "1,490", 1266.5 -> "1,266.50" (whole numbers have no decimals). */
export const aed = (n: number): string => (Number.isInteger(n) ? n.toLocaleString("en-US") : n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
export const money2 = (n: number): string => n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const cap = (s: string): string => (s ? s[0].toUpperCase() + s.slice(1).replace(/_/g, " ") : s);
export const clock = (iso: string | null | undefined): string => (iso ? new Date(iso).toISOString().slice(11, 16) : "—");
export const ymd = (iso: string | null | undefined): string => (iso ? new Date(iso).toISOString().slice(0, 10) : "—");
