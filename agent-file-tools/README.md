# agent-file-tools

**Category:** backend-helpers  
**Origin:** extracted from a production Next.js/FastAPI app.

## What it does
Glob, grep and ranged read over in-memory file rows under a per-round and per-turn character budget, with path sandboxing, tolerant tool-key normalisation, result de-duplication, truncation that says so, and a plug-in point for extra tools.

## Problem it solved
Letting a model read a repository needs hard budgets and a guard against absolute paths and `..`.

## Public interface
* `app/file_access.py`: `class ProjectScopeError`
* `app/file_access.py`: `class FileRow`
* `app/file_access.py`: `def rows_listing(rows) -> list[dict]`
* `app/file_access.py`: `def glob_to_regex(pattern: str) -> 're.Pattern'`
* `app/file_access.py`: `def grep_rows(rows, *, pattern: str, glob: str | None=None, type: str | None=None, mode: str='content', ignore_case: bool=False, context: int=0, offset: int=0, limit: int=GREP_DEFAULT_ITEMS) -> dict`
* `app/file_access.py`: `def grep_legacy(rows, pattern: str) -> list[dict]`
* `app/file_access.py`: `def read_range(code: str, offset=None, limit=None) -> dict`
* `app/file_tools.py`: `def effective_cap(raw, default: int, lo: int, hi: int) -> int`
* `app/file_tools.py`: `def normalize_flags(raw, known_keys: tuple[str, ...]) -> tuple[dict, list]`
* `app/file_tools.py`: `class FileToolTurn`
* `app/file_tools_keys.py`: `def exact_variant(key, known) -> str | None`
* `app/file_tools_models.py`: `class GlobReq`
* `app/file_tools_models.py`: `class GrepReq`
* `app/file_tools_models.py`: `class ReadReq`

## Dependencies
Python (`deps.txt`): `pydantic>=2.10`

## Stubs and what the host must provide
No stubs: every import resolves inside the module.

## Known limits
The host supplies the rows. Only the three tools are included; graph-based tools plug in through `extra_tools`.

## Quality
B (1 test file copied; built from the original executor methods)  
Tests copied: 1 (copied from the source, not run here).

## How to reuse
`FileToolTurn(rows_provider).run_round(flags, n)`.
