# node-test-alias-loader

**Category:** testing-kit  
**Origin:** extracted from a production Next.js/FastAPI app.

## What it does
A Node test loader that resolves an `@/` alias to `src/`.

## Problem it solved
`node --test` cannot read a bundler alias.

## Public interface
* (see files)

## Dependencies
None beyond the standard library.

## Stubs and what the host must provide
No stubs: every import resolves inside the module.

## Known limits
TypeScript is run by Node's own type stripping.

## Quality
A (tiny)  
Tests copied: 0 (copied from the source, not run here).

## How to reuse
`node --import ./tests/support/alias.mjs --test`.
