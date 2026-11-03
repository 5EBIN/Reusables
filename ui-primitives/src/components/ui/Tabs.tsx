'use client'

import { useId, useRef, type ReactNode } from 'react'
import { nextFocusIndex } from '@/lib/focusTrap'
import { cx, FOCUS } from '@/lib/cx'

export interface TabItem<T extends string> { id: T; label: string; badge?: ReactNode; disabled?: boolean }

/** A tab strip with its panel. Arrow keys move and select (and wrap), Home/End jump; only the active tab is in the Tab order. */
export function Tabs<T extends string>({ tabs, value, onChange, label, children, className, panelClassName = 'pt-3' }: {
  tabs: TabItem<T>[]
  value: T
  onChange: (id: T) => void
  label: string
  /** The panel of the active tab. */
  children: ReactNode
  className?: string
  /** the panel's own classes (default: a little space above it); a full-height panel passes its own */
  panelClassName?: string
}) {
  const base = useId()
  const refs = useRef<Array<HTMLButtonElement | null>>([])
  const go = (i: number) => { if (i >= 0 && !tabs[i].disabled) { onChange(tabs[i].id); refs.current[i]?.focus() } }
  return (
    <div className={className}>
      <div role="tablist" aria-label={label} className="flex gap-1 border-b border-line2">
        {tabs.map((t, i) => {
          const on = t.id === value
          return (
            <button
              key={t.id} ref={el => { refs.current[i] = el }} type="button" role="tab" id={`${base}-t-${t.id}`} aria-selected={on} aria-controls={`${base}-p-${t.id}`}
              disabled={t.disabled} tabIndex={on ? 0 : -1} onClick={() => onChange(t.id)}
              onKeyDown={e => {
                const from = tabs.findIndex(x => x.id === value)
                if (e.key === 'ArrowRight') { e.preventDefault(); go(nextFocusIndex(from, tabs.length, false)) }
                if (e.key === 'ArrowLeft') { e.preventDefault(); go(nextFocusIndex(from, tabs.length, true)) }
                if (e.key === 'Home') { e.preventDefault(); go(0) }
                if (e.key === 'End') { e.preventDefault(); go(tabs.length - 1) }
              }}
              className={cx('-mb-px inline-flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-semibold transition disabled:opacity-50', on ? 'border-accent text-t1' : 'border-transparent text-t2 hover:text-t1', FOCUS)}
            >
              {t.label}{t.badge}
            </button>
          )
        })}
      </div>
      <div role="tabpanel" id={`${base}-p-${value}`} aria-labelledby={`${base}-t-${value}`} tabIndex={0} className={cx(panelClassName, FOCUS)}>{children}</div>
    </div>
  )
}
