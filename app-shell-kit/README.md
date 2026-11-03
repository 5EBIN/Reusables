# app-shell-kit

**Category:** ui-kit  
**Origin:** extracted from a production Next.js/FastAPI app.

## What it does
Shell pieces: layout with header/sidebar slots, Ctrl+K / Ctrl+, shortcuts, `?settings=` link handling, profile menu, settings dialog with tabs, avatar, persisted collapse state.

## Problem it solved
A consistent frame around every signed-in page.

## Public interface
* `components/shell/AppShell.tsx`: `function AppShell(`
* `components/shell/Avatar.tsx`: `function Avatar(`
* `components/shell/ProfileMenu.tsx`: `function ProfileMenu(`
* `components/shell/SettingsDialog.tsx`: `function SettingsDialog()`
* `lib/shellState.ts`: `type SettingsTab`
* `lib/shellState.ts`: `const SETTINGS_TABS: ReadonlyArray<`
* `lib/shellState.ts`: `function settingsFromQuery(value: string | null): SettingsTab | null`
* `lib/shellState.ts`: `const SIDEBAR_STORAGE_KEY`
* `lib/shellState.ts`: `const parseCollapsed`
* `lib/shellState.ts`: `const PLACEHOLDER_ITEMS: ReadonlyArray<`
* `lib/shellState.ts`: `const PLACEHOLDER_PLAN_LABEL`
* `lib/shellState.ts`: `const COMING_SOON`
* `stores/shellStore.ts`: `const useShellStore`

## Dependencies
JavaScript (`deps.json`): `lucide-react`, `next`, `react`, `zustand`

## Stubs and what the host must provide
`src/app/_stubs.py` / `src/_stubs.ts` keep imports resolvable. The host must replace: `UsagePanel`, `useAuthUser`, `useSignOut`.

## Known limits
Usage panel and auth hooks are host stubs.

## Quality
B (no tests copied)  
Tests copied: 0 (copied from the source, not run here).

## How to reuse
Mount `AppShell` with your sidebar and header.

(Stub signatures were derived from the host code they stand for; they carry no behaviour.)
