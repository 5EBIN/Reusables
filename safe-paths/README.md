# safe-paths

**Category:** backend-helpers  
**Origin:** extracted from a production Next.js/FastAPI app.

## What it does
Validation (`unsafe_path_reason`), `safe_join` and `safe_write` for relative paths that came from untrusted text (model output, uploads).

## Problem it solved
Generated file paths are steerable by input; a `..` or a symlinked parent can write outside the root.

## Public interface
* `app/services/safe_paths.py`: `class UnsafePathError`
* `app/services/safe_paths.py`: `def unsafe_path_reason(rel) -> str | None`
* `app/services/safe_paths.py`: `def safe_join(root, rel) -> Path`
* `app/services/safe_paths.py`: `def safe_write(root, rel, text: str, *, encoding: str='utf-8') -> bool`

## Dependencies
None beyond the standard library.

## Stubs and what the host must provide
No stubs: every import resolves inside the module.

## Known limits
POSIX-style relative paths only; Windows drive letters and backslashes are refused, not translated.

## Quality
B (no tests copied; logic is short and covers traversal, absolute, drive, control characters, symlinked parents)  
Tests copied: 0 (copied from the source, not run here).

## How to reuse
Call `safe_join(root, rel)` before every write that uses an untrusted path.
