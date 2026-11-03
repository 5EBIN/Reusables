'use client'

import { useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { cx, FOCUS } from '@/lib/cx'

/** Code as plain text (never HTML) with a copy button. For a long file use the editor; this is for a snippet in a message, a dialog or a report. */
export function CodeBlock({ code, language, className }: { code: string; language?: string; className?: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try { await navigator.clipboard.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 1500) } catch { /* clipboard blocked: the text is still selectable */ }
  }
  return (
    <div className={cx('relative rounded-r2 border border-line2 bg-code', className)}>
      {language && <span className="absolute left-3 top-1.5 font-mono text-[10px] uppercase tracking-wide text-t3">{language}</span>}
      <button type="button" onClick={copy} aria-label={copied ? 'Copied' : 'Copy code'} className={cx('absolute right-1.5 top-1.5 inline-flex h-7 items-center gap-1 rounded-r1 px-2 text-xs text-t2 hover:bg-hover hover:text-t1', FOCUS)}>
        {copied ? <Check aria-hidden="true" size={14} /> : <Copy aria-hidden="true" size={14} />}{copied ? 'Copied' : 'Copy'}
      </button>
      <pre className={cx('overflow-x-auto px-3 pb-3 font-mono text-[13px] leading-5 text-t1', language ? 'pt-7' : 'pt-3 pr-20')}><code>{code}</code></pre>
    </div>
  )
}
