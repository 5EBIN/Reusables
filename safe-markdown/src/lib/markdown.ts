// A small markdown reader for assistant replies: **bold**, *italic* / _italic_, `inline code`, fenced code blocks, bullet and numbered lists, and [links](https://…). Nothing else.
// It produces a tree, never HTML: the renderer (components/Markdown.tsx) turns the tree into React elements, so a reply can never inject markup. Raw HTML in a reply stays text.
// Links open only http(s) and mailto addresses; any other scheme (javascript:, data:, …) is left as the text it was typed as. Pure; `.ts` imports so `node --test` can import it.

export type Inline =
  | { type: 'text'; text: string }
  | { type: 'bold'; children: Inline[] }
  | { type: 'italic'; children: Inline[] }
  | { type: 'code'; text: string }
  | { type: 'link'; href: string; children: Inline[] }

export type Block =
  | { type: 'p'; inline: Inline[] }
  | { type: 'code'; lang: string; text: string }
  | { type: 'ul' | 'ol'; items: Inline[][] }
  // only with `rich` (a document such as the spec; an assistant reply never has them)
  | { type: 'h'; level: number; inline: Inline[] }
  | { type: 'hr' }
  | { type: 'table'; header: Inline[][]; rows: Inline[][][] }

/** http, https and mailto only. */
export const isSafeHref = (href: string): boolean => /^(https?:\/\/|mailto:)[^\s]+$/i.test(href.trim())

// one token at a time, leftmost first; every pattern stays on one line and every quantifier is bounded, so an unclosed marker repeated thousands of times cannot make the scan quadratic
const TOKEN = /(`[^`\n]{1,500}`)|(\[[^\]\n]{1,200}\]\([^)\s]{1,1000}\))|(\*\*[^*\n]{1,500}?\*\*)|(__[^_\n]{1,500}?__)|(\*[^*\s\n][^*\n]{0,500}?\*)|((?<![A-Za-z0-9])_[^_\s\n][^_\n]{0,500}?_(?![A-Za-z0-9]))/
const MAX_FORMATTED = 50_000                            // a reply longer than this is shown as plain text, unformatted

export function parseInline(source: string): Inline[] {
  if (source.length > MAX_FORMATTED) return [{ type: 'text', text: source }]
  const out: Inline[] = []
  let rest = source
  const text = (s: string) => { if (s) out.push({ type: 'text', text: s }) }
  for (;;) {
    const m = TOKEN.exec(rest)
    if (!m) { text(rest); break }
    text(rest.slice(0, m.index))
    const tok = m[0]
    if (m[1]) out.push({ type: 'code', text: tok.slice(1, -1) })
    else if (m[2]) {
      const split = tok.indexOf('](')
      const label = tok.slice(1, split)
      const href = tok.slice(split + 2, -1)
      if (isSafeHref(href)) out.push({ type: 'link', href, children: parseInline(label) })
      else text(tok)                                        // an unsafe or odd link stays visible as typed
    } else if (m[3] || m[4]) out.push({ type: 'bold', children: parseInline(tok.slice(2, -2)) })
    else out.push({ type: 'italic', children: parseInline(tok.slice(1, -1)) })
    rest = rest.slice(m.index + tok.length)
  }
  return out
}

const FENCE = /^\s*```\s*([A-Za-z0-9_+-]*)\s*$/
const BULLET = /^\s*[-*+]\s+(.*)$/
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/

const HEADING = /^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$/
const RULE = /^\s{0,3}([-*_])(?:\s*\1){2,}\s*$/
const TABLE_ROW = /^\s*\|.*\|\s*$/
const TABLE_SEPARATOR = /^\s*\|?(\s*:?-{3,}:?\s*\|)+(\s*:?-{3,}:?\s*)?\|?\s*$/
const MAX_TABLE_ROWS = 500
const MAX_TABLE_CELLS = 30

const tableCells = (line: string): string[] => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim()).slice(0, MAX_TABLE_CELLS)

/** `rich` also reads headings (#), horizontal rules (---) and pipe tables: for a document (the spec), not for an assistant reply, which keeps the small reader above. */
export function parseMarkdown(source: string, opts: { rich?: boolean } = {}): Block[] {
  const lines = source.replace(/\r\n?/g, '\n').split('\n')
  const blocks: Block[] = []
  let paragraph: string[] = []
  const flush = () => { if (paragraph.length) { blocks.push({ type: 'p', inline: parseInline(paragraph.join('\n')) }); paragraph = [] } }
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const fence = FENCE.exec(line)
    if (fence) {                                           // a code block runs to the closing fence, or to the end of the reply when it was never closed
      flush()
      const body: string[] = []
      while (++i < lines.length && !FENCE.test(lines[i])) body.push(lines[i])
      blocks.push({ type: 'code', lang: fence[1], text: body.join('\n') })
      continue
    }
    if (opts.rich) {
      const heading = HEADING.exec(line)
      if (heading) { flush(); blocks.push({ type: 'h', level: heading[1].length, inline: parseInline(heading[2]) }); continue }
      if (RULE.test(line) && paragraph.length === 0) { blocks.push({ type: 'hr' }); continue }
      if (TABLE_ROW.test(line) && i + 1 < lines.length && TABLE_SEPARATOR.test(lines[i + 1])) {      // a header row, its separator, then the rows that start with |
        flush()
        const header = tableCells(line).map(parseInline)
        const rows: Inline[][][] = []
        for (i += 2; i < lines.length && TABLE_ROW.test(lines[i]) && rows.length < MAX_TABLE_ROWS; i++) rows.push(tableCells(lines[i]).map(parseInline))
        i--
        blocks.push({ type: 'table', header, rows })
        continue
      }
    }
    const kind = BULLET.test(line) ? 'ul' : NUMBERED.test(line) ? 'ol' : null
    if (kind) {
      flush()
      const pattern = kind === 'ul' ? BULLET : NUMBERED
      const items: Inline[][] = []
      for (; i < lines.length && pattern.test(lines[i]); i++) items.push(parseInline(pattern.exec(lines[i])![1]))
      i--
      blocks.push({ type: kind, items })
      continue
    }
    if (line.trim() === '') flush()
    else paragraph.push(line)
  }
  flush()
  return blocks
}
