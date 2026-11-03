import type { ReactNode } from 'react'
import { cx } from '@/lib/cx'

/** Nothing here yet: says what, and what to do about it. */
export function Empty({ icon, title, children, action, className }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cx('flex flex-col items-center gap-2 rounded-r3 border border-dashed border-ctl px-6 py-10 text-center', className)}>
      {icon && <div aria-hidden="true" className="text-t3">{icon}</div>}
      <p className="text-sm font-semibold text-t1">{title}</p>
      {children && <p className="max-w-sm text-sm text-t2">{children}</p>}
      {action && <div className="mt-1">{action}</div>}
    </div>
  )
}

/** A grey placeholder while something loads. It is hidden from a screen reader; put `aria-busy` on the region that is loading. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cx('animate-pulse rounded-r1 bg-hover', className ?? 'h-4 w-full')} />
}
