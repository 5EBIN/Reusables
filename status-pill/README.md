# status-pill

**Category:** ui-kit  
**Origin:** extracted from a production Next.js/FastAPI app.

## What it does
A status chip rendered from a kind (pass/fail/warn/info/neutral) with an icon AND a word, and a map function with an example vocabulary.

## Problem it solved
Colour alone is not a signal; unknown values must never look like a pass.

## Public interface
* `components/ui/StatusPill.tsx`: `const KIND_BOX: Record<PillKind, string>`
* `components/ui/StatusPill.tsx`: `const KIND_TEXT: Record<PillKind, string>`
* `components/ui/StatusPill.tsx`: `function StatusPill(`
* `lib/statusPill.ts`: `type PillKind`
* `lib/statusPill.ts`: `type PillIcon`
* `lib/statusPill.ts`: `interface Pill`
* `lib/statusPill.ts`: `type PillDomain`
* `lib/statusPill.ts`: `function statusPill(domain: PillDomain, value: string | null | undefined, detail?: string): Pill`
* `lib/statusPill.ts`: `const countsAsPass`

## Dependencies
JavaScript (`deps.json`): `lucide-react`

## Stubs and what the host must provide
No stubs: every import resolves inside the module.

## Known limits
The example map is invented; supply your statuses.

## Quality
A (3 tests written for the example map)  
Tests copied: 1 (copied from the source, not run here).

## How to reuse
Replace `MAP` in `lib/statusPill.ts`.
