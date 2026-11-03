import { api } from "@/lib/api-server";
import { statusOf, toView, type ApprovalsApi } from "@/lib/approvals-model";
import type { Data } from "@/app/(generated)/approvals/content";

const CODE: Record<string, string> = { pending: "p", approved: "a", rejected: "r", executed: "e" };

/** Initial list for the tab named by ?status= (default pending). Later tab changes go through the BFF in the browser. */
export async function load(params: Record<string, string | string[] | undefined> = {}, now = new Date()): Promise<Data> {
  const q = Array.isArray(params.status) ? params.status[0] : params.status;
  const code = CODE[q ?? ""] ?? "p";
  return toView(await api<ApprovalsApi>(`/v1/approvals?status=${statusOf(code)}`), code, now);
}
