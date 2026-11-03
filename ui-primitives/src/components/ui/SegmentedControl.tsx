'use client'

import { useRef } from 'react'
import { nextFocusIndex } from '@/lib/focusTrap'
import { cx, FOCUS } from '@/lib/cx'

export interface Segment<T extends string> { value: T; label: string; disabled?: boolean }

/** One choice out of a few (a radio group that looks like a pill). Arrow keys move and select; Tab leaves the group. */
export function SegmentedControl<T extends string>({ value, onChange, options, label, className }: {
  value: T
  onChange: (v: T) => void
  options: Segment<T>[]
  /** The group's accessible name. */
  label: string
  className?: string
}) {
  const refs = useRef<Array<HTMLButtonElement | null>>([])
  const move = (from: number, backwards: boolean) => {
    const enabled = options.map((o, i) => (o.disabled ? -1 : i)).filter(i => i >= 0)
    const at = nextFocusIndex(enabled.indexOf(from), enabled.length, backwards)
    if (at < 0) return
    const i = enabled[at]
    onChange(options[i].value)
    refs.current[i]?.focus()
  }
  return (
    <div role="radiogroup" aria-label={label} className={cx('inline-flex gap-0.5 rounded-r2 border border-line2 bg-sunk p-0.5', className)}>
      {options.map((o, i) => {
        const on = o.value === value
        return (
          <button
            key={o.value} ref={el => { refs.current[i] = el }} type="button" role="radio" aria-checked={on} disabled={o.disabled} tabIndex={on ? 0 : -1}
            onClick={() => onChange(o.value)}
            onKeyDown={e => {
              if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); move(i, false) }
              if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); move(i, true) }
            }}
            className={cx('h-7 rounded-r1 px-3 text-xs font-semibold transition disabled:opacity-50', on ? 'bg-card text-t1 shadow-sh1' : 'text-t2 hover:text-t1', FOCUS)}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
