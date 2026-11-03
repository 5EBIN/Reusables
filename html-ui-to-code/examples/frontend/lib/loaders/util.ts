import { api, ApiError } from "@/lib/api-server";

/** Server-side API call that never throws for data problems: returns null (and the status) so a page can show a notice instead of crashing.
 *  Authentication failures (401) are rethrown so the route gate can send the person to sign in. */
export async function tryApi<T>(path: string, init?: RequestInit & { org?: boolean }): Promise<{ data: T | null; status: number }> {
  try {
    return { data: await api<T>(path, init), status: 200 };
  } catch (e) {
    if (e instanceof ApiError) {
      if (e.status === 401) throw e;
      return { data: null, status: e.status };
    }
    return { data: null, status: 0 };
  }
}

/** Short message for a failed section; "" when everything loaded. */
export function failure(...statuses: number[]): string {
  const bad = statuses.find((s) => s !== 200);
  if (bad === undefined) return "";
  return bad === 403 ? "You do not have access to some of this data." : "Some data could not be loaded. Try again.";
}
