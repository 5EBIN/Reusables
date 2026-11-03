# Checks, set 2 (public)

Files checked: 183 (our new files only).

## py_compile
42 .py files; failures: 0

## tsc --noEmit --allowJs --skipLibCheck (stubs, no installs, frontend node_modules used read-only for type declarations)

Syntax errors are TS1xxx codes. Other errors (type or missing-type declarations, because stubs are typed `any` and some packages are not resolvable) are counted, not hidden.

| Module | TS files | All errors | Syntax errors |
|---|---|---|---|
| app-shell-kit | 7 | 8 | 0 |
| command-palette | 2 | 5 | 0 |
| diff-view | 2 | 0 | 0 |
| file-tree | 3 | 0 | 0 |
| hero-carousel | 3 | 1 | 0 |
| hitl-approval-kit-v2 | 3 | 0 | 0 |
| password-strength | 3 | 4 | 0 |
| safe-markdown | 2 | 0 | 0 |
| status-pill | 2 | 5 | 0 |
| ui-primitives | 23 | 4 | 0 |
| ui-tokens-theme | 3 | 0 | 0 |
| visual-editor-wrapper | 12 | 17 | 0 |

## Dangling-import check (both parts together)
Unresolved imports: 0; public importing private: 0

## Secrets scan (keys, JWT, Bearer, sk-/sb_ values, postgres URLs with passwords, emails, UUIDs, platform hosts)
Hits: 0

## Anonymity scan (original names, customer/sample names; file contents, file names, folder names)
Hits: 0
