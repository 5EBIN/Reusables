import type { ReactNode } from 'react'
import { parseMarkdown, type Inline } from '@/lib/markdown'

/** An assistant reply as markdown (bold, italics, inline code, code blocks, lists, links). Built from lib/markdown's tree, so there is no raw HTML anywhere: reply text is only ever text.
 *  Styled with classes and the app's colour tokens (no inline colours): the Tailwind reset removes list markers, so `list-disc` / `list-decimal` bring them back. */
function renderInline(nodes: Inline[]): ReactNode[] {
  return nodes.map((n, i) => {
    switch (n.type) {
      case 'text':
        return n.text.split('\n').flatMap((line, j) => (j === 0 ? [line] : [<br key={`${i}-br${j}`} />, line]))
      case 'bold': return <strong key={i} className="font-semibold text-[var(--green-light)]">{renderInline(n.children)}</strong>
      case 'italic': return <em key={i}>{renderInline(n.children)}</em>
      case 'code': return <code key={i} className="rounded bg-black/30 px-1 py-px font-mono text-[0.92em]">{n.text}</code>
      case 'link': return <a key={i} href={n.href} target="_blank" rel="noopener noreferrer" className="text-[var(--green-light)] underline">{renderInline(n.children)}</a>
    }
  })
}

/** `rich` is for a document (the spec): headings, rules and tables as well. An assistant reply is not `rich`. */
export default function Markdown({ text, rich = false }: { text: string; rich?: boolean }) {
  return (
    <div className="whitespace-normal break-words">
      {parseMarkdown(text, { rich }).map((b, i) => {
        if (b.type === 'h') return <p key={i} role="heading" aria-level={Math.min(b.level + 2, 6)} className={b.level <= 2 ? 'mt-4 text-base font-semibold text-t1 first:mt-0' : 'mt-3 text-sm font-semibold text-t1 first:mt-0'}>{renderInline(b.inline)}</p>
        if (b.type === 'hr') return <hr key={i} className="my-3 border-line2" />
        if (b.type === 'table') {
          return (
            <div key={i} className="mt-2 overflow-x-auto rounded-md border border-line2 first:mt-0">
              <table className="w-full border-collapse text-left text-sm">
                <thead><tr className="bg-sunk">{b.header.map((h, j) => <th key={j} scope="col" className="border-b border-line2 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-t3">{renderInline(h)}</th>)}</tr></thead>
                <tbody>{b.rows.map((r, j) => <tr key={j} className="border-b border-line last:border-b-0 align-top">{r.map((c, k) => <td key={k} className="px-3 py-2">{renderInline(c)}</td>)}</tr>)}</tbody>
              </table>
            </div>
          )
        }
        if (b.type === 'code') {
          return <pre key={i} className="mt-2 overflow-x-auto whitespace-pre rounded-md bg-black/35 px-2.5 py-2 font-mono text-[0.92em] first:mt-0"><code>{b.text}</code></pre>
        }
        if (b.type === 'p') return <p key={i} className="mt-2 first:mt-0">{renderInline(b.inline)}</p>
        const List = b.type
        const marker = b.type === 'ul' ? 'list-disc' : 'list-decimal'
        return <List key={i} className={`mt-2 pl-5 first:mt-0 marker:text-[var(--text-muted)] ${marker}`}>{b.items.map((item, j) => <li key={j}>{renderInline(item)}</li>)}</List>
      })}
    </div>
  )
}
