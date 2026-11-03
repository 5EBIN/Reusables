# command-palette

**Category:** ui-kit  
**Origin:** extracted from a production Next.js/FastAPI app.

## What it does
A Ctrl+K command palette: command list from the host's pages, theme and settings commands, word filter, arrow-key focus, Enter to run.

## Problem it solved
Keyboard navigation across a big app.

## Public interface
* `components/shell/CommandPalette.tsx`: `function CommandPalette(`
* `lib/commands.ts`: `interface Page`
* `lib/commands.ts`: `type CommandAction`
* `lib/commands.ts`: `interface Command`
* `lib/commands.ts`: `function commandList(pages: readonly Page[]): Command[]`
* `lib/commands.ts`: `function filterCommands(list: readonly Command[], query: string): Command[]`
* `lib/commands.ts`: `type ShellShortcut`
* `lib/commands.ts`: `function shortcutFor(e:`

## Dependencies
JavaScript (`deps.json`): `next`, `react`

## Stubs and what the host must provide
No stubs: every import resolves inside the module.

## Known limits
Needs the shell store and Next router (stubs/third-party).

## Quality
B (no tests copied)  
Tests copied: 0 (copied from the source, not run here).

## How to reuse
Pass `pages` to `CommandPalette`.
