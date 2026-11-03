import type { ElementType, ReactNode } from 'react'
import { cx, FOCUS } from '@/lib/cx'

/** A surface. `as="button"`/`"a"` makes the whole card the control (it gets the focus ring and a hover state). */
export function Card({ as: As = 'div', title, actions, children, className, ...rest }: {
  as?: ElementType
  title?: ReactNode
  actions?: ReactNode
  children?: ReactNode
  className?: string
  [key: string]: unknown
}) {
  const interactive = As === 'button' || As === 'a'
  return (
    <As className={cx('block w-full rounded-r3 border border-line2 bg-card p-4 text-left text-t1 shadow-sh1', interactive && cx('transition hover:bg-hover', FOCUS), className)} {...rest}>
      {(title || actions) && (
        <div className="mb-3 flex items-center justify-between gap-2">
          {title && <h3 className="text-sm font-semibold">{title}</h3>}
          {actions}
        </div>
      )}
      {children}
    </As>
  )
}

/** Apple-settings style rows: one rounded group, a hairline between rows, a label on the left and a control or value on the right. */
export function GroupedList({ label, children, className }: { label?: string; children: ReactNode; className?: string }) {
  return (
    <section className={className}>
      {label && <h3 className="mb-1.5 px-1 text-xs font-semibold uppercase tracking-wide text-t3">{label}</h3>}
      <ul className="divide-y divide-line overflow-hidden rounded-r3 border border-line2 bg-card">{children}</ul>
    </section>
  )
}

export function GroupedRow({ label, hint, children, onClick }: { label: ReactNode; hint?: ReactNode; children?: ReactNode; onClick?: () => void }) {
  const body = (
    <>
      <span className="min-w-0 flex-1">
        <span className="block text-sm text-t1">{label}</span>
        {hint && <span className="mt-0.5 block text-xs text-t3">{hint}</span>}
      </span>
      {children && <span className="flex shrink-0 items-center gap-2 text-sm text-t2">{children}</span>}
    </>
  )
  return (
    <li>
      {onClick
        ? <button type="button" onClick={onClick} className={cx('flex w-full items-center gap-3 px-3.5 py-2.5 text-left transition hover:bg-hover', FOCUS)}>{body}</button>
        : <div className="flex items-center gap-3 px-3.5 py-2.5">{body}</div>}
    </li>
  )
}
