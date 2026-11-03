import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import { cx } from '@/lib/cx'

const TONE = {
  info:  { cls: 'border-info/30 bg-info/10', icon: Info, color: 'text-info' },
  warn:  { cls: 'border-warn/30 bg-warn/10', icon: AlertTriangle, color: 'text-warn' },
  fail:  { cls: 'border-fail/30 bg-fail/10', icon: XCircle, color: 'text-fail' },
  pass:  { cls: 'border-pass/30 bg-pass/10', icon: CheckCircle2, color: 'text-pass' },
}
export type NoticeTone = keyof typeof TONE

/** A message that stays on the page. A problem (`fail`, `warn`) is announced as an alert; the rest politely. */
export function Notice({ tone = 'info', title, children, action, className }: { tone?: NoticeTone; title?: string; children?: ReactNode; action?: ReactNode; className?: string }) {
  const t = TONE[tone]
  const Icon = t.icon
  return (
    <div role={tone === 'fail' || tone === 'warn' ? 'alert' : 'status'} className={cx('flex items-start gap-2.5 rounded-r2 border px-3 py-2.5 text-sm text-t1', t.cls, className)}>
      <Icon aria-hidden="true" size={16} strokeWidth={1.5} className={cx('mt-0.5 shrink-0', t.color)} />
      <div className="min-w-0 flex-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={cx('text-t2', title && 'mt-0.5')}>{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}
