import type { ReactNode } from 'react'
import { cx } from '@/lib/cx'

/** A small label that classifies something (a method, a layer, a framework). It is not a status: use StatusPill for that. */
export function Tag({ children, mono = false, className }: { children: ReactNode; mono?: boolean; className?: string }) {
  return <span className={cx('inline-flex items-center rounded-r1 border border-line2 bg-sunk px-1.5 py-px text-[11px] leading-4 text-t2', mono && 'font-mono', className)}>{children}</span>
}

/** A number beside a label (open items, findings). Zero is shown, not hidden: "0" is information. */
export function Count({ value, tone = 'neutral', label, className }: { value: number; tone?: 'neutral' | 'warn' | 'fail'; label?: string; className?: string }) {
  const tones = { neutral: 'bg-hover text-t2', warn: 'bg-warn/15 text-warn', fail: 'bg-fail/15 text-fail' }
  return (
    <span aria-label={label ? `${value} ${label}` : undefined} className={cx('inline-flex min-w-[20px] items-center justify-center rounded-full px-1.5 text-[11px] font-semibold leading-5', tones[tone], className)}>
      {value}
    </span>
  )
}
