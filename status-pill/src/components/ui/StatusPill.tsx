import {
  AlertTriangle, BadgeCheck, Bot, Check, CheckCircle2, CircleDashed, Clock, FileClock, HelpCircle, History, Info, Loader2, Lock, Search, ServerCrash, ShieldCheck,
  Sparkles, Trash2, UserCheck, X, XCircle, type LucideIcon,
} from 'lucide-react'
import type { Pill, PillIcon, PillKind } from '@/lib/statusPill'
import { cx } from '@/lib/cx'

const ICONS: Record<PillIcon, LucideIcon> = {
  'check-circle-2': CheckCircle2, 'x-circle': XCircle, 'alert-triangle': AlertTriangle, 'circle-dashed': CircleDashed, history: History, 'shield-check': ShieldCheck, lock: Lock,
  'help-circle': HelpCircle, 'user-check': UserCheck, bot: Bot, sparkles: Sparkles, 'badge-check': BadgeCheck, x: X, 'server-crash': ServerCrash, 'file-clock': FileClock,
  search: Search, check: Check, 'loader-2': Loader2, clock: Clock, 'trash-2': Trash2, info: Info,
}

/** Text colour and a soft tint per kind. The tint is the kind's own colour at low strength, so it follows the theme. */
const KIND_CLASS: Record<PillKind, string> = {
  pass: 'text-pass bg-pass/10 border-pass/30',
  fail: 'text-fail bg-fail/10 border-fail/30',
  warn: 'text-warn bg-warn/10 border-warn/30',
  info: 'text-info bg-info/10 border-info/30',
  ai: 'text-ai bg-ai/10 border-ai/30',
  neutral: 'text-t2 bg-hover border-line2',
  locked: 'text-locked bg-locked/10 border-locked/30',
}

/** The same kinds as a tinted box (a status block that holds more than a word) and as text, so a screen never picks a colour of its own. */
export const KIND_BOX: Record<PillKind, string> = {
  pass: 'border-pass/30 bg-pass/10', fail: 'border-fail/30 bg-fail/10', warn: 'border-warn/30 bg-warn/10', info: 'border-info/30 bg-info/10',
  ai: 'border-ai/30 bg-ai/10', neutral: 'border-line2 bg-hover', locked: 'border-locked/30 bg-locked/10',
}
export const KIND_TEXT: Record<PillKind, string> = {
  pass: 'text-pass', fail: 'text-fail', warn: 'text-warn', info: 'text-info', ai: 'text-ai', neutral: 'text-t2', locked: 'text-locked',
}

/** Colour + icon + word, never colour alone. It takes a Pill from lib/statusPill.ts and decides nothing itself. */
export function StatusPill({ pill, className }: { pill: Pill; className?: string }) {
  const Icon = ICONS[pill.icon]
  return (
    <span className={cx('inline-flex flex-col items-start', className)}>
      <span className={cx('inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold leading-5', KIND_CLASS[pill.kind], pill.dashed && 'border-dashed')} data-kind={pill.kind}>
        <Icon aria-hidden="true" size={14} strokeWidth={1.5} className={pill.icon === 'loader-2' ? 'animate-spin' : undefined} />
        {pill.label}
        {pill.check && <Check aria-hidden="true" size={12} strokeWidth={2} />}
      </span>
      {pill.detail && <span className="mt-0.5 text-[11px] leading-4 text-t3">{pill.detail}</span>}
    </span>
  )
}
