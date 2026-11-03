import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { cx, FOCUS } from '@/lib/cx'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md'

const VARIANT: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-accent-fg hover:brightness-110',
  secondary: 'bg-card text-t1 border border-ctl hover:bg-hover',
  ghost: 'bg-transparent text-t2 hover:bg-hover hover:text-t1',
  danger: 'bg-fail text-accent-fg hover:brightness-110',
}
const SIZE: Record<ButtonSize, string> = { sm: 'h-7 px-2.5 text-xs', md: 'h-9 px-3.5 text-sm' }

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  /** A request is running: the button is disabled and says so to a screen reader; its label stays. */
  loading?: boolean
  icon?: ReactNode
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'secondary', size = 'md', loading = false, icon, className, children, disabled, type = 'button', ...rest }, ref,
) {
  return (
    <button
      ref={ref} type={type} disabled={disabled || loading} aria-busy={loading || undefined}
      className={cx('inline-flex items-center justify-center gap-1.5 rounded-r2 font-semibold transition disabled:cursor-not-allowed disabled:opacity-50', VARIANT[variant], SIZE[size], FOCUS, className)}
      {...rest}
    >
      {loading ? <span aria-hidden="true" className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" /> : icon}
      {children}
    </button>
  )
})

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'aria-label'> {
  /** Required: an icon has no text of its own. Also the tooltip. */
  label: string
  variant?: Exclude<ButtonVariant, 'primary'>
  size?: ButtonSize
  children: ReactNode
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { label, variant = 'ghost', size = 'md', className, children, type = 'button', ...rest }, ref,
) {
  return (
    <button
      ref={ref} type={type} aria-label={label} title={label}
      className={cx('inline-flex items-center justify-center rounded-r2 transition disabled:cursor-not-allowed disabled:opacity-50', VARIANT[variant], size === 'sm' ? 'h-7 w-7' : 'h-9 w-9', FOCUS, className)}
      {...rest}
    >
      {children}
    </button>
  )
})
