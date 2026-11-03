// The shell's own state, as pure functions (the store in stores/shellStore.ts only holds it): Settings tabs, the `?settings=` link that /account redirects to, and the saved sidebar width. Erasable TypeScript only.
export type SettingsTab = 'general' | 'account' | 'usage'

export const SETTINGS_TABS: ReadonlyArray<{ id: SettingsTab; label: string }> = [
  { id: 'general', label: 'General' },
  { id: 'account', label: 'Account' },
  { id: 'usage', label: 'Usage and billing' },
]

const isSettingsTab = (v: unknown): v is SettingsTab => v === 'general' || v === 'account' || v === 'usage'

/** The tab named by `?settings=<tab>` (what /account redirects to so an old link still opens Settings); null when the link does not ask for Settings. A bare `?settings` or an unknown value opens General. */
export function settingsFromQuery(value: string | null): SettingsTab | null {
  if (value === null) return null
  return isSettingsTab(value) ? value : 'general'
}

export const SIDEBAR_STORAGE_KEY = 'app-sidebar-collapsed'

/** Anything but the exact saved string "true" is expanded. */
export const parseCollapsed = (raw: string | null): boolean => raw === 'true'

/** Profile-menu entries and the plan label that nothing backs yet: shown, dimmed, tagged "Soon", with no action. To wire one up, give it a real item in components/shell/ProfileMenu.tsx and delete it here; to drop them, empty this list. */
export const PLACEHOLDER_ITEMS: ReadonlyArray<{ id: 'language' | 'upgrade'; label: string }> = [
  { id: 'language', label: 'Language' },
  { id: 'upgrade', label: 'Upgrade plan' },
]
export const PLACEHOLDER_PLAN_LABEL = 'Pro'
export const COMING_SOON = 'Coming soon'
