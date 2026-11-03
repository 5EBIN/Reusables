# diff-view

**Category:** frontend-lib  
**Origin:** extracted from a production Next.js/FastAPI app.

## What it does
A side-by-side diff on Monaco's diff editor, theme aware, loaded lazily.

## Problem it solved
A readable review of a change.

## Public interface
* `components/review/DiffView.tsx`: `interface DiffViewProps`
* `components/review/DiffView.tsx`: `function DiffView(`
* `lib/language.ts`: `function getLanguage(path: string): string`

## Dependencies
JavaScript (`deps.json`): `@monaco-editor/react`, `next`, `react`

## Stubs and what the host must provide
No stubs: every import resolves inside the module.

## Known limits
Monaco is a heavy dependency.

## Quality
B  
Tests copied: 0 (copied from the source, not run here).

## How to reuse
`<DiffView original modified path />`.
