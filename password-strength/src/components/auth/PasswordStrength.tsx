import { Check } from 'lucide-react'
import { STRENGTH_META } from '@/lib/passwordStrength'
import type { PasswordAnalysis } from '@/lib/passwordStrength'
import { cx } from '@/lib/cx'

function CheckItem({ ok, label }: { ok: boolean; label: string }) {
  return (
    <li className="flex items-center gap-1.5 text-xs text-t3">
      <span aria-hidden="true" className={cx('flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full border', ok ? 'border-pass bg-pass/15 text-pass' : 'border-line2')}>
        {ok && <Check size={9} strokeWidth={3} />}
      </span>
      {label}<span className="sr-only">{ok ? ': met' : ': not met'}</span>
    </li>
  )
}

/** The strength bar and the checklist of what a password still needs (shared by sign-up and reset password). */
export function PasswordStrength({ analysis }: { analysis: PasswordAnalysis | null }) {
  if (!analysis) return null
  const meta = STRENGTH_META[analysis.strength]
  const { checks } = analysis
  return (
    <div className="mt-2.5 flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <div className="flex flex-1 gap-1">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-[3px] flex-1 rounded-full transition-colors" style={{ background: i <= meta.segments ? meta.color : 'var(--line2)' }} />
          ))}
        </div>
        <span role="status" className="min-w-[36px] text-right text-xs font-semibold" style={{ color: meta.color }}>{meta.label}</span>
      </div>

      <ul className="grid grid-cols-2 gap-x-3 gap-y-1">
        <CheckItem ok={checks.length}    label="8+ characters" />
        <CheckItem ok={checks.uppercase} label="Uppercase (A–Z)" />
        <CheckItem ok={checks.digit}     label="Number (0–9)" />
        <CheckItem ok={checks.special}   label="Special (!@#…)" />
        <CheckItem ok={checks.notCommon} label="Not a common password" />
        <CheckItem ok={checks.lowercase} label="Lowercase (a–z)" />
      </ul>

      {analysis.isCommon && <p role="alert" className="text-xs font-semibold text-fail">This password appears in breach databases. Choose another.</p>}
    </div>
  )
}
