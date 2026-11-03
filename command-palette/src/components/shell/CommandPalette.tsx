'use client'

import { useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Dialog, Input } from '@/components/ui'
import { useTheme } from '@/hooks/useTheme'
import { commandList, filterCommands, type Command, type Page } from '@/lib/commands'
import { nextFocusIndex } from '@/lib/focusTrap'
import { useShellStore } from '@/stores/shellStore'
import { cx } from '@/lib/cx'

/** Ctrl+K: type to find a page, a theme or Settings. Arrow keys move through the matches, Enter runs one, Esc closes. */
export default function CommandPalette({ pages }: { pages: readonly Page[] }) {
  const router = useRouter()
  const { setPref } = useTheme()
  const open = useShellStore(s => s.paletteOpen)
  const setPaletteOpen = useShellStore(s => s.setPaletteOpen)
  const openSettings = useShellStore(s => s.openSettings)
  const setNewProjectOpen = useShellStore(s => s.setNewProjectOpen)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)

  const matches = useMemo(() => filterCommands(commandList(pages), query), [pages, query])
  const close = () => { setPaletteOpen(false); setQuery(''); setActive(0) }

  const run = (c: Command) => {
    close()
    switch (c.action.type) {
      case 'go': router.push(c.action.href); break
      case 'theme': setPref(c.action.pref); break
      case 'settings': openSettings(); break
      case 'new-project': setNewProjectOpen(true); break
    }
  }

  return (
    <Dialog open={open} title="Search and commands" onClose={close}>
      <Input
        data-autofocus="" role="combobox" aria-expanded="true" aria-controls="palette-list" aria-activedescendant={matches[active] ? `palette-${matches[active].id}` : undefined} aria-label="Type a command"
        placeholder="Go to a page, switch theme…" value={query}
        onChange={e => { setQuery(e.target.value); setActive(0) }}
        onKeyDown={e => {
          if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); e.stopPropagation(); setActive(nextFocusIndex(active, matches.length, e.key === 'ArrowUp')) }
          else if (e.key === 'Enter' && matches[active]) { e.preventDefault(); run(matches[active]) }
        }}
      />
      <ul id="palette-list" role="listbox" aria-label="Commands" className="mt-2 max-h-72 overflow-y-auto">
        {matches.length === 0 && <li className="px-2 py-3 text-sm text-t3">No command matches</li>}
        {matches.map((c, i) => (
          <li key={c.id} id={`palette-${c.id}`} role="option" aria-selected={i === active} onMouseMove={() => setActive(i)} onClick={() => run(c)}
            className={cx('flex cursor-pointer items-baseline justify-between gap-3 rounded-r1 px-2.5 py-1.5 text-sm', i === active ? 'bg-sel text-t1' : 'text-t2')}>
            <span><span className="mr-2 text-xs text-t3">{c.group}</span>{c.label}</span>
            {c.hint && <span className="shrink-0 text-xs text-t3">{c.hint}</span>}
          </li>
        ))}
      </ul>
    </Dialog>
  )
}
