import type { ReactNode } from 'react'
import { cx } from '@/lib/cx'
import type { PillKind } from '@/lib/statusPill'

export interface TimelineItem { id: string; title: ReactNode; time?: string; kind?: PillKind; children?: ReactNode }

const DOT: Record<PillKind, string> = { pass: 'bg-pass', fail: 'bg-fail', warn: 'bg-warn', info: 'bg-info', ai: 'bg-ai', neutral: 'bg-t3', locked: 'bg-locked' }

/** Things in the order they happened, with a dot in the colour of what kind of thing it was. The dot is decoration: the title says it in words. */
export function Timeline({ items, className }: { items: TimelineItem[]; className?: string }) {
  return (
    <ol className={cx('relative ml-1.5 border-l border-line2', className)}>
      {items.map(it => (
        <li key={it.id} className="relative pb-4 pl-5 last:pb-0">
          <span aria-hidden="true" className={cx('absolute -left-[5px] top-1.5 h-2.5 w-2.5 rounded-full ring-2 ring-card', DOT[it.kind ?? 'neutral'])} />
          <div className="flex items-baseline justify-between gap-3">
            <p className="text-sm font-semibold text-t1">{it.title}</p>
            {it.time && <time className="shrink-0 text-xs text-t3">{it.time}</time>}
          </div>
          {it.children && <div className="mt-0.5 text-sm text-t2">{it.children}</div>}
        </li>
      ))}
    </ol>
  )
}
