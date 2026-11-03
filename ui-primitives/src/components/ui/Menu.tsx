'use client'

import { Fragment, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { nextFocusIndex } from '@/lib/focusTrap'
import { cx, FOCUS } from '@/lib/cx'
import { COMING_SOON } from '@/lib/shellState'
import { Tag } from './Tag'

export interface MenuItem { id: string; label: string; icon?: ReactNode; danger?: boolean; disabled?: boolean; shortcut?: string; separatorBefore?: boolean; inactive?: string; onSelect: () => void }

/** A button that opens a list of actions. An item with `inactive` (its tag, e.g. "Soon") is shown dimmed and aria-disabled with the text as its tooltip: it can be focused but does nothing on click or Enter. Arrow keys move (and wrap), Enter/Space choose, Esc and a click outside close it and give the focus back to the button. */
export function Menu({ trigger, items, label, align = 'left', side = 'bottom', header, triggerClassName, triggerLabel, className }: {
  /** What the button shows. */
  trigger: ReactNode
  items: MenuItem[]
  /** The menu's accessible name. */
  label: string
  align?: 'left' | 'right'
  /** which side of the button it opens on: `top` for a button at the bottom of the screen */
  side?: 'bottom' | 'top'
  /** shown above the items (who is signed in, say); not a menu item */
  header?: ReactNode
  /** replaces the default bordered-button look of the trigger (an avatar, an icon) */
  triggerClassName?: string
  /** the trigger's accessible name when it shows no text */
  triggerLabel?: string
  className?: string
}) {
  const [open, setOpen] = useState(false)
  const id = useId()
  const button = useRef<HTMLButtonElement>(null)
  const root = useRef<HTMLDivElement>(null)
  const rows = useRef<Array<HTMLButtonElement | null>>([])
  const enabled = items.map((it, i) => (it.disabled ? -1 : i)).filter(i => i >= 0)

  useEffect(() => {
    if (!open) return
    rows.current[enabled[0]]?.focus()
    const onDown = (e: MouseEvent) => { if (!root.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  const close = () => { setOpen(false); button.current?.focus() }
  const step = (from: number, backwards: boolean) => {
    const at = nextFocusIndex(enabled.indexOf(from), enabled.length, backwards)
    if (at >= 0) rows.current[enabled[at]]?.focus()
  }

  return (
    <div ref={root} className={cx('relative inline-block', className)}>
      <button
        ref={button} type="button" aria-haspopup="menu" aria-expanded={open} aria-controls={open ? id : undefined} aria-label={triggerLabel}
        onClick={() => setOpen(o => !o)}
        onKeyDown={e => { if (e.key === 'ArrowDown' && !open) { e.preventDefault(); setOpen(true) } }}
        className={cx(triggerClassName ?? 'inline-flex h-9 items-center gap-1.5 rounded-r2 border border-ctl bg-card px-3 text-sm font-semibold text-t1 transition hover:bg-hover', FOCUS)}
      >
        {trigger}
      </button>
      {open && (
        <div
          id={id} role="menu" aria-label={label}
          onKeyDown={e => {
            if (e.key === 'Escape') { e.stopPropagation(); close() }
            if (e.key === 'Tab') setOpen(false)
          }}
          className={cx('absolute z-50 min-w-[200px] rounded-r2 border border-line2 bg-card p-1 shadow-sh2', side === 'top' ? 'bottom-full mb-1' : 'mt-1', align === 'right' ? 'right-0' : 'left-0')}
        >
          {header && <div className="border-b border-line px-2.5 pb-2 pt-1.5">{header}</div>}
          {items.map((it, i) => (
            <Fragment key={it.id}>
            {it.separatorBefore && <div role="separator" className="my-1 h-px bg-line" />}
            <button
              ref={el => { rows.current[i] = el }} type="button" role="menuitem" disabled={it.disabled} tabIndex={-1}
              aria-disabled={it.inactive ? true : undefined} title={it.inactive ? COMING_SOON : undefined}
              onClick={() => { if (it.inactive) return; it.onSelect(); close() }}
              onKeyDown={e => {
                if (e.key === 'ArrowDown') { e.preventDefault(); step(i, false) }
                if (e.key === 'ArrowUp') { e.preventDefault(); step(i, true) }
              }}
              className={cx('flex w-full items-center gap-2 rounded-r1 px-2.5 py-1.5 text-left text-sm transition hover:bg-hover disabled:opacity-50', it.danger ? 'text-fail' : 'text-t1', it.inactive && 'cursor-default opacity-60 hover:bg-transparent', FOCUS)}
            >
              {it.icon}<span className="flex-1">{it.label}</span>{it.shortcut && <kbd className="font-mono text-[11px] text-t3">{it.shortcut}</kbd>}{it.inactive && <Tag>{it.inactive}</Tag>}
            </button>
            </Fragment>
          ))}
        </div>
      )}
    </div>
  )
}
