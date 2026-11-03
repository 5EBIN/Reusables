'use client'

import { ChevronsUpDown, CircleArrowUp, CreditCard, Languages, LifeBuoy, LogOut, Puzzle, Settings, type LucideIcon } from 'lucide-react'
import { Menu, type MenuItem } from '@/components/ui'
import { useSignOut } from '@/_stubs'
import { useAuthUser } from '@/_stubs'
import { useShellStore } from '@/stores/shellStore'
import { PLACEHOLDER_ITEMS, PLACEHOLDER_PLAN_LABEL } from '@/lib/shellState'
import { Avatar } from './Avatar'

// Where "Get help" goes. No address is invented: without NEXT_PUBLIC_CONTACT_EMAIL the item is not shown (same rule as the landing page's "Book a demo").
const HELP_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL

const PLACEHOLDER_ICON: Record<typeof PLACEHOLDER_ITEMS[number]['id'], LucideIcon> = { language: Languages, upgrade: CircleArrowUp, vscode: Puzzle }

/** The profile button at the bottom left of the sidebar and its menu. Collapsing the sidebar keeps the avatar. */
export function ProfileMenu({ collapsed }: { collapsed: boolean }) {
  const signOut = useSignOut()
  const user = useAuthUser()
  const openSettings = useShellStore(s => s.openSettings)
  const name = user?.name ?? '…'

  const items: MenuItem[] = [
    { id: 'settings', label: 'Settings', icon: <Settings aria-hidden="true" size={15} />, shortcut: 'Ctrl+,', onSelect: () => openSettings('general') },
    { id: 'usage', label: 'Usage', icon: <CreditCard aria-hidden="true" size={15} />, onSelect: () => openSettings('usage') },
    ...PLACEHOLDER_ITEMS.map(({ id, label }): MenuItem => { const Icon = PLACEHOLDER_ICON[id]; return { id, label, icon: <Icon aria-hidden="true" size={15} />, inactive: 'Soon', onSelect: () => {} } }),
    ...(HELP_EMAIL ? [{ id: 'help', label: 'Get help', icon: <LifeBuoy aria-hidden="true" size={15} />, onSelect: () => { window.location.href = `mailto:${HELP_EMAIL}?subject=Platform%20help` } }] : []),
    {
      id: 'logout', label: 'Log out', icon: <LogOut aria-hidden="true" size={15} />, danger: true, separatorBefore: true,
      onSelect: signOut,
    },
  ]

  return (
    <Menu
      side="top" label="Profile" triggerLabel={`Profile: ${name}`} className="w-full"
      triggerClassName="flex w-full items-center gap-2.5 rounded-r2 px-1.5 py-1.5 text-left transition hover:bg-hover"
      header={<><p className="truncate text-sm font-semibold text-t1">{name}</p><p className="truncate text-xs text-t3">{user?.email ?? ''}</p></>}
      items={items}
      trigger={
        <>
          <Avatar name={name} />
          {!collapsed && (
            <>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold text-t1">{name}</span>
                <span className="block truncate text-xs text-t3">{PLACEHOLDER_PLAN_LABEL}</span>
              </span>
              <ChevronsUpDown aria-hidden="true" size={14} className="shrink-0 text-t3" />
            </>
          )}
        </>
      }
    />
  )
}
