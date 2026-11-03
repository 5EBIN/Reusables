import type { ReactNode } from 'react'
import { cx } from '@/lib/cx'

/** Facts as label / value pairs (a real definition list, so a screen reader reads each pair together). */
export function KeyValue({ items, className }: { items: Array<{ label: string; value: ReactNode; mono?: boolean; title?: string }>; className?: string }) {
  return (
    <dl className={cx('grid grid-cols-[minmax(110px,max-content)_1fr] gap-x-4 gap-y-1.5 text-sm', className)}>
      {items.map(it => (
        <div key={it.label} className="contents">
          <dt title={it.title} className="text-t3">{it.label}</dt>
          <dd className={cx('min-w-0 break-words text-t1', it.mono && 'font-mono text-[13px]')}>{it.value}</dd>
        </div>
      ))}
    </dl>
  )
}
