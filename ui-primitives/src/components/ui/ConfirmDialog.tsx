'use client'

import Dialog from './Dialog'
import { Button } from './Button'

interface Props {
  open: boolean
  title: string
  message: string
  confirmLabel: string
  /** a destructive action: the confirm button is red and Cancel has the focus */
  danger?: boolean
  onConfirm: () => void
  onCancel: () => void
}

/** Replaces the browser's confirm(): the question, Cancel and one confirm button. */
export default function ConfirmDialog({ open, title, message, confirmLabel, danger = false, onConfirm, onCancel }: Props) {
  return (
    <Dialog open={open} title={title} onClose={onCancel}>
      <p style={{ margin: '0 0 18px', fontSize: 13.5, lineHeight: 1.5, color: 'var(--text-muted)' }}>{message}</p>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <Button data-autofocus={danger ? '' : undefined} onClick={onCancel}>Cancel</Button>
        <Button variant={danger ? 'danger' : 'primary'} data-autofocus={danger ? undefined : ''} onClick={onConfirm}>{confirmLabel}</Button>
      </div>
    </Dialog>
  )
}
