import { useState } from 'react'

export interface ApprovalCardProps {
  title: string
  detail?: string
  onResolve: (status: 'approved' | 'rejected' | 'revision_requested', feedback: string) => void | Promise<void>
}

/** A generic approval card: approve, reject, or ask for a revision (which needs a reason). */
export function ApprovalCard({ title, detail, onResolve }: ApprovalCardProps) {
  const [feedback, setFeedback] = useState('')
  const [busy, setBusy] = useState(false)
  const run = async (status: 'approved' | 'rejected' | 'revision_requested') => {
    setBusy(true)
    try { await onResolve(status, feedback.trim()) } finally { setBusy(false) }
  }
  return (
    <section aria-label={title}>
      <h3>{title}</h3>
      {detail ? <p>{detail}</p> : null}
      <label>
        Reason (needed to request a revision)
        <textarea value={feedback} onChange={e => setFeedback(e.target.value)} />
      </label>
      <button disabled={busy} onClick={() => run('approved')}>Approve</button>
      <button disabled={busy} onClick={() => run('rejected')}>Reject</button>
      <button disabled={busy || !feedback.trim()} onClick={() => run('revision_requested')}>Request revision</button>
    </section>
  )
}
