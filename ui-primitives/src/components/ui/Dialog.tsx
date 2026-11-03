'use client'

import { useEffect, useId, useRef, type ReactNode } from 'react'
import { nextFocusIndex } from '@/lib/focusTrap'
import { backdropAction, escapeAction } from '@/lib/dialogKeys'

const FOCUSABLE = 'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

interface Props {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
  /** A decision is pending: a click on the backdrop and Esc do nothing (the dialog closes only through its own buttons). */
  blocking?: boolean
  /** Where the panel sits: the middle of the screen (default) or a full-height sheet on the right (components/ui/Sheet.tsx). The focus trap, Esc and blocking behave the same. */
  placement?: 'center' | 'right'
  /** The panel's width in px (default 420 in the middle, 480 on the right), never wider than the screen. */
  width?: number
}

/** A modal dialog: focus moves into it and is kept inside (Tab / Shift+Tab wrap), Esc and a backdrop click close it unless `blocking`, and focus returns to where it was when it closes. */
export default function Dialog({ open, title, onClose, children, blocking = false, placement = 'center', width }: Props) {
  const panel = useRef<HTMLDivElement>(null)
  const titleId = useId()

  useEffect(() => {
    if (!open) return
    const before = document.activeElement as HTMLElement | null
    const first = panel.current?.querySelector<HTMLElement>('[data-autofocus]') ?? panel.current?.querySelector<HTMLElement>(FOCUSABLE)
    ;(first ?? panel.current)?.focus()
    return () => before?.focus?.()
  }, [open])

  if (!open) return null

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      if (escapeAction(blocking) === 'close') { e.stopPropagation(); onClose() }
      return
    }
    if (e.key !== 'Tab') return
    const items = [...(panel.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])]
    const next = nextFocusIndex(items.indexOf(document.activeElement as HTMLElement), items.length, e.shiftKey)
    e.preventDefault()
    if (next >= 0) items[next].focus()
    else panel.current?.focus()
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 1000, display: 'flex', alignItems: placement === 'right' ? 'stretch' : 'center', justifyContent: placement === 'right' ? 'flex-end' : 'center', padding: placement === 'right' ? 0 : 16 }} onKeyDown={onKeyDown}>
      <div aria-hidden="true" onClick={backdropAction(blocking) === 'close' ? onClose : undefined} style={{ position: 'absolute', inset: 0, background: 'var(--scrim)' }} />
      <div
        ref={panel} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}
        style={{ position: 'relative', width: `min(${width ?? (placement === 'right' ? 480 : 420)}px, 100%)`, background: 'var(--card)', border: '1px solid var(--line2)', borderRadius: placement === 'right' ? 'var(--r3) 0 0 var(--r3)' : 'var(--r3)', padding: 20, color: 'var(--t1)', boxShadow: 'var(--sh2)', outline: 'none', overflowY: 'auto', maxHeight: placement === 'right' ? undefined : '92vh' }}
      >
        <h2 id={titleId} style={{ margin: '0 0 12px', fontSize: 16, fontWeight: 600 }}>{title}</h2>
        {children}
      </div>
    </div>
  )
}
