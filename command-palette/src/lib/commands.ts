// The command palette (Ctrl+K): which commands exist, which match what was typed, and which keys open it and Settings. Pure data, no React, erasable TypeScript only (node --test imports it).
export interface Page { id: string; path: string; label: string }
import type { ThemePref } from './theme.ts'

export type CommandAction =
  | { type: 'go'; href: string }
  | { type: 'theme'; pref: ThemePref }
  | { type: 'settings' }
  | { type: 'new-project' }

export interface Command { id: string; label: string; group: 'Go to' | 'Appearance' | 'Open' | 'Create'; action: CommandAction; hint?: string }

/** Every command: the host's pages, the theme choices, Settings and New. */
export function commandList(pages: readonly Page[]): Command[] {
  const list: Command[] = [{ id: 'go-projects', label: 'Projects', group: 'Go to', action: { type: 'go', href: '/dashboard' } }]
  for (const p of pages) list.push({ id: `go-${p.id}`, label: p.label, group: 'Go to', action: { type: 'go', href: `/${p.path}` } })
  list.push(
    { id: 'theme-auto', label: 'Theme: Automatic', group: 'Appearance', action: { type: 'theme', pref: 'auto' } },
    { id: 'theme-light', label: 'Theme: Light', group: 'Appearance', action: { type: 'theme', pref: 'light' } },
    { id: 'theme-dark', label: 'Theme: Dark', group: 'Appearance', action: { type: 'theme', pref: 'dark' } },
  )
  list.push({ id: 'new-project', label: 'New project', group: 'Create', action: { type: 'new-project' } })
  list.push({ id: 'settings', label: 'Open Settings', group: 'Open', action: { type: 'settings' }, hint: 'Ctrl+,' })
  return list
}

/** The commands whose label contains every word typed (any case); an empty query keeps all, in order. */
export function filterCommands(list: readonly Command[], query: string): Command[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean)
  return list.filter(c => { const hay = `${c.label} ${c.hint ?? ''}`.toLowerCase(); return words.every(w => hay.includes(w)) })
}

export type ShellShortcut = 'palette' | 'settings' | null

/** Ctrl+K (or Cmd+K) opens the palette, Ctrl+, (or Cmd+,) opens Settings. Anything else, and a key with Shift or Alt held, is not ours. */
export function shortcutFor(e: { key: string; ctrlKey: boolean; metaKey: boolean; shiftKey: boolean; altKey: boolean }): ShellShortcut {
  if (!(e.ctrlKey || e.metaKey) || e.shiftKey || e.altKey) return null
  if (e.key.toLowerCase() === 'k') return 'palette'
  if (e.key === ',') return 'settings'
  return null
}
