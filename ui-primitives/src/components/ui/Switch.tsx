import { cx, FOCUS } from '@/lib/cx'

/** An on/off setting that applies at once. The label is real text beside it (or `label` for a screen reader when the row already shows one). */
export function Switch({ checked, onChange, label, disabled, className }: {
  checked: boolean
  onChange: (next: boolean) => void
  label: string
  disabled?: boolean
  className?: string
}) {
  return (
    <button
      type="button" role="switch" aria-checked={checked} aria-label={label} disabled={disabled} onClick={() => onChange(!checked)}
      className={cx('relative inline-flex h-6 w-10 shrink-0 items-center rounded-full border transition disabled:cursor-not-allowed disabled:opacity-50', checked ? 'border-accent bg-accent' : 'border-ctl bg-sunk', FOCUS, className)}
    >
      <span aria-hidden="true" className={cx('inline-block h-4 w-4 rounded-full transition-transform', checked ? 'translate-x-[18px] bg-accent-fg' : 'translate-x-[3px] bg-t3')} />
    </button>
  )
}
