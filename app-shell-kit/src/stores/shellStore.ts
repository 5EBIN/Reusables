import { create } from 'zustand'
import { parseCollapsed, SIDEBAR_STORAGE_KEY, type SettingsTab } from '@/lib/shellState'

interface ShellState {
  /** the sidebar shows icons only (the avatar stays); saved per browser */
  collapsed: boolean
  toggleCollapsed: () => void
  /** read the saved choice (after mount: the server render cannot know it) */
  loadCollapsed: () => void
  settings: { open: boolean; tab: SettingsTab }
  openSettings: (tab?: SettingsTab) => void
  closeSettings: () => void
  setSettingsTab: (tab: SettingsTab) => void
  paletteOpen: boolean
  setPaletteOpen: (open: boolean) => void
  newProjectOpen: boolean
  setNewProjectOpen: (open: boolean) => void
  decisionsOpen: boolean
  setDecisionsOpen: (open: boolean) => void
}

/** What the app shell shows: the sidebar width, and which of Settings, the command palette and the Decisions sheet is open. Per-viewer conveniences only; nothing here is project data. */
export const useShellStore = create<ShellState>((set, get) => ({
  collapsed: false,
  loadCollapsed: () => { try { set({ collapsed: parseCollapsed(localStorage.getItem(SIDEBAR_STORAGE_KEY)) }) } catch { /* blocked storage: expanded */ } },
  toggleCollapsed: () => {
    const next = !get().collapsed
    try { localStorage.setItem(SIDEBAR_STORAGE_KEY, String(next)) } catch { /* private window: applies to this page only */ }
    set({ collapsed: next })
  },
  settings: { open: false, tab: 'general' },
  openSettings: (tab) => set((s) => ({ settings: { open: true, tab: tab ?? s.settings.tab }, paletteOpen: false })),
  closeSettings: () => set((s) => ({ settings: { ...s.settings, open: false } })),
  setSettingsTab: (tab) => set((s) => ({ settings: { ...s.settings, tab } })),
  paletteOpen: false,
  setPaletteOpen: (open) => set({ paletteOpen: open }),
  newProjectOpen: false,
  setNewProjectOpen: (open) => set({ newProjectOpen: open }),
  decisionsOpen: false,
  setDecisionsOpen: (open) => set({ decisionsOpen: open }),
}))
