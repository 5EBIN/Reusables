# pdf-report-engine

**Category:** backend-helpers  
**Origin:** extracted from a production Next.js/FastAPI app.

## What it does
A deterministic PDF layer on reportlab: embedded OFL fonts only, A4 grid, running header, 'Page X of Y' footer, tables with fixed column presets that split across pages, status badges, key/value and scorecard blocks, a stacked bar, overflow appendix, breakable paths, outline bookmarks, and byte-identical output for the same input. Includes one invented example report.

## Problem it solved
Reports looked different between runs, long paths broke layouts, tables left headings behind, and base-14 fonts leaked in.

## Public interface
* `app/pdf/report_kit.py`: `def TS(cmds: list) -> TableStyle`
* `app/pdf/report_kit.py`: `def plural(n, word: str, many: str | None=None) -> str`
* `app/pdf/report_kit.py`: `class ReportIntegrityError`
* `app/pdf/report_kit.py`: `def register_fonts() -> None`
* `app/pdf/report_kit.py`: `def font_hashes() -> dict`
* `app/pdf/report_kit.py`: `def font_hash() -> str`
* `app/pdf/report_kit.py`: `def natural_key(value) -> list`
* `app/pdf/report_kit.py`: `def clean(value) -> str`
* `app/pdf/report_kit.py`: `def is_path_like(token: str) -> bool`
* `app/pdf/report_kit.py`: `def breakable(text: str, min_len: int=40, avail_pt: float | None=None, font: str | None=None, size: float=8.5) -> str`
* `app/pdf/report_kit.py`: `def mono(value, size: float=8, wrap: bool=True, avail_pt: float | None=None) -> str`
* `app/pdf/report_kit.py`: `def short_hash(digest: str, n: int=16) -> str`
* `app/pdf/report_kit.py`: `class Overflow`
* `app/pdf/report_kit.py`: `def styles() -> dict`
* `app/pdf/report_kit.py`: `def worst(*statuses: str) -> str`
* `app/pdf/report_kit.py`: `def rank(status: str) -> int`
* `app/pdf/report_kit.py`: `def category_to_badge(status: str) -> str`
* `app/pdf/report_kit.py`: `def assert_reconciled(total: int, parts: dict, what: str='counts') -> None`
* `app/pdf/report_kit.py`: `def P(text, style='body') -> Paragraph`
* `app/pdf/report_kit.py`: `def PM(markup, style='body') -> Paragraph`
* `app/pdf/report_kit.py`: `def heading(text: str, level: int=2) -> list`
* `app/pdf/report_kit.py`: `def bullets(items, style='bullet') -> list`
* `app/pdf/report_kit.py`: `def badge(status: str, width_mm: float=34) -> Table`
* `app/pdf/report_kit.py`: `def table(rows: list, columns, *, header: bool=True, mono_cols: tuple=(), status_col: int | None=None, num_cols: tuple=(), status_map: dict | None=None, overflow: Overflow | None=None, where: str='table', split_in_row: bool=False) -> list`
* `app/pdf/report_kit.py`: `def key_value(pairs: list, mono_values: tuple=()) -> list`
* `app/pdf/report_kit.py`: `def scorecard(title: str, cards: list) -> list`
* `app/pdf/report_kit.py`: `def stacked_bar(segments: list, caption: str='') -> Drawing`
* `app/pdf/report_kit.py`: `def canonical(inputs)`
* `app/pdf/report_kit.py`: `def inputs_json(inputs) -> str`
* `app/pdf/report_kit.py`: `def inputs_hash(inputs) -> str`
* `app/pdf/report_kit.py`: `def compose(story: list) -> list`
* `app/pdf/report_kit.py`: `class Document`
* `app/pdf/report_kit.py`: `def fit(text: str, font: str, size: float, width: float) -> str`
* `app/pdf/report_kit.py`: `def render_bytes(story: list, *, title: str, project: str, project_id: str, doc_id: str, subject: str, author: str, run_context: dict | None, inputs) -> bytes`
* `app/pdf/report_kit.py`: `def write_pdf(path: str, data: bytes, inputs) -> str`
* `app/pdf/report_kit.py`: `def is_completed(ctx: dict | None) -> bool`
* `app/pdf/report_kit.py`: `def walk_text(flowables) -> list`
* `app/pdf/run_context.py`: `def now_iso() -> str`
* `app/pdf/run_context.py`: `def new_run_context(run_outcome: str=COMPLETED, *, trigger: str='', abort_reason: str | None=None, generated_at: str | None=None, run_id: str | None=None) -> dict`
* `app/pdf/run_context.py`: `def header(ctx: dict | None, document: str) -> dict`
* ... and 6 more

## Dependencies
Python (`deps.txt`): `reportlab>=4.0.0`

## Stubs and what the host must provide
No stubs: every import resolves inside the module.

## Known limits
Not included: cover page, table of contents, markdown/HTML to PDF and right-to-left text (see the roadmap in public/README.md). Glyphs missing from the fonts print as '?'.

## Quality
B (2 tests copied for the sample report)  
Tests copied: 1 (copied from the source, not run here).

## How to reuse
Build a story from `heading`, `table`, `key_value`, then `render_bytes(...)`.
