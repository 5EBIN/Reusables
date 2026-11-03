'use client'

import { Button, Dialog, GroupedList, GroupedRow, KeyValue, SegmentedControl, Tabs } from '@/components/ui'
import { useAuthUser } from '@/_stubs'
import { useSignOut } from '@/_stubs'
import { useTheme } from '@/hooks/useTheme'
import { SETTINGS_TABS } from '@/lib/shellState'
import type { ThemePref } from '@/lib/theme'
import { useShellStore } from '@/stores/shellStore'
import { Avatar } from './Avatar'
import { UsagePanel } from '@/_stubs'

const THEMES: Array<{ value: ThemePref; label: string }> = [{ value: 'auto', label: 'Automatic' }, { value: 'light', label: 'Light' }, { value: 'dark', label: 'Dark' }]

function GeneralPanel() {
  const { pref, setPref } = useTheme()
  return (
    <div className="flex flex-col gap-5">
      <GroupedList label="Appearance">
        <GroupedRow label="Theme" hint="Automatic follows your system">
          <SegmentedControl label="Theme" value={pref} onChange={setPref} options={THEMES} />
        </GroupedRow>
      </GroupedList>
    </div>
  )
}

function AccountPanel() {
  const user = useAuthUser()
  const signOut = useSignOut()
  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <Avatar name={user?.name ?? 'U'} size={48} />
        <div className="min-w-0"><p className="truncate text-base font-semibold text-t1">{user?.name ?? '…'}</p><p className="text-xs text-t3">Signed in</p></div>
      </div>
      <KeyValue items={[{ label: 'Name', value: user?.name ?? '—' }, { label: 'Email', value: user?.email || '—', mono: true }]} />
      <GroupedList label="Session">
        <GroupedRow label="Sign out on this device"><Button size="sm" variant="danger" onClick={signOut}>Sign out</Button></GroupedRow>
      </GroupedList>
    </div>
  )
}

/** Settings (General, Account, Usage and billing): one dialog, opened from the profile menu, Ctrl+, or the palette, on every page. */
export default function SettingsDialog() {
  const { open, tab } = useShellStore(s => s.settings)
  const closeSettings = useShellStore(s => s.closeSettings)
  const setSettingsTab = useShellStore(s => s.setSettingsTab)
  return (
    <Dialog open={open} title="Settings" width={680} onClose={closeSettings}>
      <Tabs label="Settings sections" tabs={[...SETTINGS_TABS]} value={tab} onChange={setSettingsTab}>
        <div className="max-h-[60vh] overflow-y-auto pr-1">
          {tab === 'general' && <GeneralPanel />}
          {tab === 'account' && <AccountPanel />}
          {tab === 'usage' && <UsagePanel />}
        </div>
      </Tabs>
      <div className="mt-4 flex justify-end"><Button onClick={closeSettings}>Done</Button></div>
    </Dialog>
  )
}
