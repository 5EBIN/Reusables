// A queue of pending approvals: add by id (never twice), remove by id, merge a re-read of the server's pending list after a reconnect.
// Pure (no React) so `node --test` can import it.
export interface PendingApproval { approval_id: string; action: string; details?: Record<string, unknown> }

export function enqueue(queue: PendingApproval[], a: PendingApproval): PendingApproval[] {
  return queue.some(p => p.approval_id === a.approval_id) ? queue : [...queue, a]
}

export function dequeue(queue: PendingApproval[], id: string): PendingApproval[] {
  return queue.filter(p => p.approval_id !== id)
}

/** After a reconnect: keep what is still pending on the server, add what arrived while disconnected, drop what was decided meanwhile, never duplicate. */
export function mergePending(queue: PendingApproval[], serverPending: PendingApproval[]): PendingApproval[] {
  const ids = new Set(serverPending.map(p => p.approval_id))
  const kept = queue.filter(p => ids.has(p.approval_id))
  const have = new Set(kept.map(p => p.approval_id))
  return [...kept, ...serverPending.filter(p => !have.has(p.approval_id))]
}

/** An approval_resolved event removes its request whatever the status was (approved, rejected, revision_requested or expired). */
export function onResolved(queue: PendingApproval[], event: { approval_id?: unknown }): PendingApproval[] {
  return typeof event.approval_id === "string" ? dequeue(queue, event.approval_id) : queue
}
