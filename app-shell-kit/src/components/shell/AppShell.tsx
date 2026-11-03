'use client'

import { Suspense, useEffect, type ReactNode } from 'react'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { shortcutFor } from '@/lib/commands'
import { settingsFromQuery } from '@/lib/shellState'
import { useShellStore } from '@/stores/shellStore'
import CommandPalette from './CommandPalette'
import SettingsDialog from './SettingsDialog'
import type { Page } from '@/lib/commands'

/** `?settings=<tab>` opens Settings over whatever page this is, then leaves the address clean. /account redirects here, so an old link still works. */
function SettingsFromLink() {
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const openSettings = useShellStore(s => s.openSettings)
  useEffect(() => {
    const tab = settingsFromQuery(params.get('settings'))
    if (!tab) return
    openSettings(tab)
    router.replace(pathname)
  }, [params, pathname, router, openSettings])
  return null
}

/** The frame of every signed-in page: a header slot, a sidebar slot, the page, and the things that open over it. Ctrl+K opens the palette and Ctrl+, opens Settings from anywhere. */
export default function AppShell({ pages, header, sidebar, extras, children }: { pages: readonly Page[]; header?: ReactNode; sidebar?: ReactNode; extras?: ReactNode; children: ReactNode }) {
  const loadCollapsed = useShellStore(s => s.loadCollapsed)
  const setPaletteOpen = useShellStore(s => s.setPaletteOpen)
  const openSettings = useShellStore(s => s.openSettings)

  useEffect(() => { loadCollapsed() }, [loadCollapsed])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented) return          // the code editor claims Ctrl+K as the start of its own chords
      const which = shortcutFor(e)
      if (!which) return
      e.preventDefault()
      if (which === 'palette') setPaletteOpen(true)
      else openSettings()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [setPaletteOpen, openSettings])

  return (
    <div className="flex h-full flex-col overflow-hidden bg-bg text-t1">
      {header}
      <div className="flex min-h-0 flex-1">
        {sidebar}
        <main className="relative min-h-0 min-w-0 flex-1 overflow-y-auto">{children}</main>
      </div>
      <Suspense fallback={null}><SettingsFromLink /></Suspense>
      <SettingsDialog />
      <CommandPalette pages={pages} />
      {extras}
    </div>
  )
}
