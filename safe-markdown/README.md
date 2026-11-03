# safe-markdown

**Category:** frontend-lib  
**Origin:** extracted from a production Next.js/FastAPI app.

## What it does
A small markdown parser that produces a tree and a React renderer that never injects raw HTML.

## Problem it solved
Rendering model or user text as HTML invites XSS.

## Public interface
* `components/Markdown.tsx`: `function Markdown(`
* `lib/markdown.ts`: `type Inline`
* `lib/markdown.ts`: `type Block`
* `lib/markdown.ts`: `const isSafeHref`
* `lib/markdown.ts`: `function parseInline(source: string): Inline[]`
* `lib/markdown.ts`: `function parseMarkdown(source: string, opts:`

## Dependencies
JavaScript (`deps.json`): `react`

## Stubs and what the host must provide
No stubs: every import resolves inside the module.

## Known limits
Supports a subset of markdown.

## Quality
B (no markdown tests copied)  
Tests copied: 0 (copied from the source, not run here).

## How to reuse
`<Markdown text=... />`.
