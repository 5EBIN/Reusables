import { cx } from '@/lib/cx'

/** The person's initial in a circle. Solid accent, no gradient. */
export function Avatar({ name, size = 28, className }: { name: string; size?: number; className?: string }) {
  return (
    <span
      aria-hidden="true" style={{ width: size, height: size, fontSize: Math.round(size * 0.43) }}
      className={cx('inline-flex shrink-0 items-center justify-center rounded-full bg-accent font-bold text-accent-fg', className)}
    >
      {(name.trim()[0] ?? 'U').toUpperCase()}
    </span>
  )
}
