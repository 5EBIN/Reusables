'use client'

import { useId, useState, type ReactNode } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { Input } from '@/components/ui'
import { cx, FOCUS } from '@/lib/cx'

/** A password box with its label and a show / hide button (sign in, sign up, reset password). `labelAction` sits at the right of the label row ("Forgot password?"). */
export function PasswordField({ label, value, onChange, placeholder = '••••••••', minLength, autoComplete = 'current-password', labelAction }: {
  label: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  minLength?: number
  autoComplete?: string
  labelAction?: ReactNode
}) {
  const id = useId()
  const [show, setShow] = useState(false)
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-2">
        <label htmlFor={id} className="text-xs font-semibold text-t2">{label}</label>
        {labelAction}
      </div>
      <div className="relative">
        <Input
          id={id} type={show ? 'text' : 'password'} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
          required minLength={minLength} autoComplete={show ? 'off' : autoComplete} className="pr-10"
        />
        <button
          type="button" onClick={() => setShow(v => !v)} aria-label={show ? 'Hide password' : 'Show password'} aria-pressed={show}
          className={cx('absolute right-1.5 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-r1 text-t3 hover:text-t1', FOCUS)}
        >
          {show ? <Eye aria-hidden="true" size={16} /> : <EyeOff aria-hidden="true" size={16} />}
        </button>
      </div>
    </div>
  )
}
