# untrusted-text-fence-v2

**Category:** backend-helpers  
**Origin:** extracted from a production Next.js/FastAPI app.

**Variant of:** `llm-provider-adapter` (existing module). **How it differs:** its wrapper is a `<data>` tag with personal-data redaction; this one adds a source label, a notice line and marker neutralisation.

## What it does
`wrap_untrusted(source, text)` fences untrusted text as labelled data and replaces any copy of the fence markers inside it; `is_wrapped` checks a string.

## Problem it solved
A file or web page can contain instructions aimed at the model (prompt injection).

## Public interface
* `app/agents/untrusted.py`: `def wrap_untrusted(source: str, text: str) -> str`
* `app/agents/untrusted.py`: `def is_wrapped(text: str) -> bool`

## Dependencies
None beyond the standard library.

## Stubs and what the host must provide
No stubs: every import resolves inside the module.

## Known limits
A fence reduces, not removes, injection risk; keep tool permissions narrow too.

## Quality
B (no tests copied; 20 lines)  
Tests copied: 0 (copied from the source, not run here).

## How to reuse
Pass every untrusted string through `wrap_untrusted` before it goes into a prompt.
