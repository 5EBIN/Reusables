'use client'

import { useState } from 'react'
import { X } from 'lucide-react'
import { addTag } from '@/lib/tagInput'
import { cx, FOCUS } from '@/lib/cx'

/** A list of short values typed one at a time (roles, domains). Enter or a comma adds, Backspace on an empty box removes the last, each tag has a remove button. */
export function TagInput({ value, onChange, label, placeholder, className }: { value: string[]; onChange: (next: string[]) => void; label: string; placeholder?: string; className?: string }) {
  const [draft, setDraft] = useState('')
  const commit = () => { const next = addTag(value, draft); if (next !== value) onChange(next); setDraft('') }
  return (
    <div className={cx('flex min-h-9 flex-wrap items-center gap-1.5 rounded-r2 border border-ctl bg-card px-2 py-1 focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-info', className)}>
      {value.map(t => (
        <span key={t} className="inline-flex items-center gap-1 rounded-r1 border border-line2 bg-sunk px-1.5 py-px text-xs text-t1">
          {t}
          <button type="button" aria-label={`Remove ${t}`} onClick={() => onChange(value.filter(x => x !== t))} className={cx('rounded-sm text-t3 hover:text-t1', FOCUS)}><X aria-hidden="true" size={12} /></button>
        </span>
      ))}
      <input
        aria-label={label} value={draft} placeholder={value.length ? undefined : placeholder} onChange={e => setDraft(e.target.value)} onBlur={commit}
        onKeyDown={e => {
          if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); commit() }
          else if (e.key === 'Backspace' && !draft && value.length) onChange(value.slice(0, -1))
        }}
        className="min-w-[96px] flex-1 bg-transparent py-1 text-sm text-t1 outline-none placeholder:text-t3"
      />
    </div>
  )
}
