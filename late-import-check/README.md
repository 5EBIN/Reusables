# late-import-check

**Category:** testing-kit  
**Origin:** extracted from a production Next.js/FastAPI app.

## What it does
A script that finds function-local imports that should be at module level, and the test that fails the build when one appears.

## Problem it solved
Late imports hide circular dependencies and slow first calls.

## Public interface
* (see files)

## Dependencies
None beyond the standard library.

## Stubs and what the host must provide
No stubs: every import resolves inside the module.

## Known limits
Allow-listing for deliberate lazy imports is in the script.

## Quality
A (5 tests copied)  
Tests copied: 1 (copied from the source, not run here).

## How to reuse
Run the script in CI.
