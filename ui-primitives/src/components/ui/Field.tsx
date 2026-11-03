'use client'

import { cloneElement, isValidElement, useId, type InputHTMLAttributes, type ReactElement, type ReactNode, type Ref, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { cx, FOCUS } from '@/lib/cx'

const CONTROL = 'w-full rounded-r2 border bg-card px-3 text-sm text-t1 placeholder:text-t3 transition disabled:cursor-not-allowed disabled:opacity-50'
const border = (invalid?: boolean) => (invalid ? 'border-fail' : 'border-ctl')

/** A label, the control, a hint and an error. The control gets the id, and `aria-describedby` / `aria-invalid`, so a screen reader reads all of it. */
export function Field({ label, hint, error, children, className }: { label: string; hint?: ReactNode; error?: ReactNode; children: ReactElement<Record<string, unknown>>; className?: string }) {
  const id = useId()
  const describedBy = [error ? `${id}-err` : '', hint ? `${id}-hint` : ''].filter(Boolean).join(' ') || undefined
  return (
    <div className={cx('flex flex-col gap-1', className)}>
      <label htmlFor={id} className="text-xs font-semibold text-t2">{label}</label>
      {isValidElement(children) ? cloneElement(children, { id, 'aria-describedby': describedBy, 'aria-invalid': error ? true : undefined }) : children}
      {hint && <p id={`${id}-hint`} className="text-xs text-t3">{hint}</p>}
      {error && <p id={`${id}-err`} role="alert" className="text-xs font-semibold text-fail">{error}</p>}
    </div>
  )
}

export function Input({ invalid, className, ...rest }: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean; ref?: Ref<HTMLInputElement> }) {
  return <input className={cx(CONTROL, 'h-9', border(invalid), FOCUS, className)} {...rest} />
}

export function Select({ invalid, className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean; ref?: Ref<HTMLSelectElement> }) {
  return <select className={cx(CONTROL, 'h-9', border(invalid), FOCUS, className)} {...rest}>{children}</select>
}

export function Textarea({ invalid, className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean; ref?: Ref<HTMLTextAreaElement> }) {
  return <textarea className={cx(CONTROL, 'min-h-[84px] py-2', border(invalid), FOCUS, className)} {...rest} />
}
