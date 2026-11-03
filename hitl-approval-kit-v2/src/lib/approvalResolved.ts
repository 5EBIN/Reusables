// The SSE `approval_resolved` event {approval_id, status, approved, action, file_path?, feedback?, revision?}. What it may trigger is decided HERE, from `status` (or the boolean `approved`), never from a
// field that is missing: an event without either means "not approved". Pure (no React); `.ts` imports so `node --test` can import it.

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v)

/** Approval actions whose approval makes the backend resume the paused work. Resuming is right only for the actions listed here; anything unknown resumes nothing. */
export const RESUME_ACTIONS: ReadonlySet<string> = new Set(["example_review"])

/** `revision` and `feedback` come from the backend (a rejection WITH a reason that sent the item back for revision); older events carry neither. */
export interface Resolved { status: string | null; approved: boolean; action: string; filePath: string; revision: boolean; feedback: string }

/** The decision in an approval_resolved payload. `status` wins; `approved` is the fallback; neither present = not approved. */
export function resolvedApproval(data: unknown): Resolved {
  const d = isObj(data) ? data : {}
  const status = typeof d.status === "string" && d.status ? d.status : null
  const approved = status !== null ? status === "approved" : d.approved === true
  return {
    status, approved, action: typeof d.action === "string" ? d.action : "", filePath: typeof d.file_path === "string" ? d.file_path : "",
    revision: d.revision === true, feedback: typeof d.feedback === "string" ? d.feedback.trim() : "",
  }
}

/** True only for an APPROVED decision on an action type that resumes the paused work. Rejected, expired, declined and unknown decisions never do. */
export function shouldResume(data: unknown): boolean {
  const r = resolvedApproval(data)
  return r.approved && RESUME_ACTIONS.has(r.action)
}

/** The activity-feed line: Approved / Expired / Revision requested / Rejected. "Revision requested: <reason>" only when the backend says the rejection was a revision (the `revision` flag, with its reason);
 *  a plain rejection, and declined or any other non-approval, read as Rejected. Never guessed from the wording. */
export function resolvedText(data: unknown): string {
  const r = resolvedApproval(data)
  if (r.approved) return `✓ Approved: ${r.filePath}`
  if (r.status === "expired") return `⏱ Expired: ${r.filePath}`
  if (r.revision && r.feedback) return `↻ Revision requested: ${r.feedback}`
  return `✗ Rejected: ${r.filePath}`
}
