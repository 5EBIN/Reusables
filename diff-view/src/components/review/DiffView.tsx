'use client'

// Shared diff renderer — Phase 6 of the sidebar transform.
//
// Before this component existed, three independent implementations rendered
// diffs: the Code tab's "mini diff" (hand-rolled LCS), the full-page Monaco
// DiffEditor, and ApprovalCard's raw code_preview slice. The first two are
// unified here; both `mode='mini'` and `mode='full'` derive from the exact
// same `{ original, modified }` pair passed in — never independent
// computation — so they can never disagree about what changed.
//
// `mode='mini'`: truncated hunk view (first 80 lines of each side, ±2 lines
// of context around each change, capped at 35 rendered rows) — a teaser,
// not a complete diff. Pass `onExpand` to make it clickable through to the
// full view on the identical pair.
// `mode='full'`: Monaco's DiffEditor, read-only, side-by-side, whole file.

import dynamic from 'next/dynamic'
import { useMemo } from 'react'
import { getLanguage } from '@/lib/language'
import { useTheme } from '@/hooks/useTheme'

const MonacoDiffEditor = dynamic(
  () => import('@monaco-editor/react').then(m => ({ default: m.DiffEditor })),
  { ssr: false }
)

export interface DiffViewProps {
  original: string
  modified: string
  filePath: string
  mode: 'mini' | 'full'
  /** mini mode only — renders a "view full diff" affordance when provided */
  onExpand?: () => void
  /** full mode only — Monaco editor height (default '100%') */
  height?: string
}

type MiniLine = { type: 'add' | 'del' | 'ctx'; text: string }

// Port of the original miniDiffLines memo (previously inline in code/page.tsx,
// ~line 922-955) — same algorithm, same limits, now shared.
function computeMiniDiff(original: string, modified: string): MiniLine[] | null {
  const aLines = (original ?? '').split('\n').slice(0, 80)
  const bLines = (modified ?? '').split('\n').slice(0, 80)
  const m = aLines.length, n = bLines.length
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0))
  for (let i = 1; i <= m; i++)
    for (let j = 1; j <= n; j++)
      dp[i][j] = aLines[i - 1] === bLines[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1])

  const all: MiniLine[] = []
  let i = m, j = n
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && aLines[i - 1] === bLines[j - 1]) {
      all.unshift({ type: 'ctx', text: aLines[i - 1] }); i--; j--
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      all.unshift({ type: 'add', text: bLines[j - 1] }); j--
    } else {
      all.unshift({ type: 'del', text: aLines[i - 1] }); i--
    }
  }

  const changedIdx: number[] = []
  all.forEach((r, idx) => { if (r.type !== 'ctx') changedIdx.push(idx) })
  if (changedIdx.length === 0) return null

  const visible = new Set<number>()
  changedIdx.forEach(idx => {
    for (let k = Math.max(0, idx - 2); k <= Math.min(all.length - 1, idx + 2); k++) visible.add(k)
  })
  return all.filter((_, idx) => visible.has(idx)).slice(0, 35)
}

export function DiffView({ original, modified, filePath, mode, onExpand, height = '100%' }: DiffViewProps) {
  const { monacoTheme } = useTheme()
  const miniLines = useMemo(
    () => (mode === 'mini' ? computeMiniDiff(original, modified) : null),
    [mode, original, modified],
  )

  if (mode === 'full') {
    return (
      <MonacoDiffEditor
        height={height}
        language={getLanguage(filePath)}
        original={original}
        modified={modified}
        theme={monacoTheme}
        options={{ readOnly: true, fontSize: 13, fontFamily: 'var(--mono)', minimap: { enabled: false }, scrollBeyondLastLine: false, wordWrap: 'on', renderSideBySide: true }}
      />
    )
  }

  if (!miniLines || miniLines.length === 0) return null

  return (
    <div style={{ borderRadius: 10, border: '1px solid var(--border)', overflow: 'hidden', background: 'var(--surface)' }}>
      <div style={{ maxHeight: 200, overflowY: 'auto', fontFamily: 'var(--mono)', fontSize: 10.5, lineHeight: 1.65 }}>
        {miniLines.map((line, idx) => (
          <div key={idx} style={{
            padding: '0 10px',
            background: line.type === 'add' ? 'color-mix(in srgb, var(--accent) 10%, transparent)' : line.type === 'del' ? 'color-mix(in srgb, var(--fail) 10%, transparent)' : 'transparent',
            color: line.type === 'add' ? 'var(--accent)' : line.type === 'del' ? 'var(--fail)' : 'var(--text-dim)',
            display: 'flex', gap: 8,
          }}>
            <span style={{ flexShrink: 0, opacity: 0.65, userSelect: 'none', width: 9 }}>
              {line.type === 'add' ? '+' : line.type === 'del' ? '-' : ' '}
            </span>
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{line.text || ' '}</span>
          </div>
        ))}
      </div>
      {onExpand && (
        <div style={{ padding: '4px 10px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', background: 'var(--bg)' }}>
          <button
            onClick={onExpand}
            style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--info)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
          >
            view full diff ▸
          </button>
        </div>
      )}
    </div>
  )
}
