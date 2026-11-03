# file-tree

**Category:** frontend-lib  
**Origin:** extracted from a production Next.js/FastAPI app.

## What it does
Flat paths to a nested tree (folders first), per-scope persisted open/closed state, and a virtualised react-arborist wrapper.

## Problem it solved
Large file lists need a tree that stays fast.

## Public interface
* `components/FileTree.tsx`: `interface FileTreeProps`
* `components/FileTree.tsx`: `function FileTree(`
* `lib/fileTreeState.ts`: `type OpenMap`
* `lib/fileTreeState.ts`: `const treeOpenKey`
* `lib/fileTreeState.ts`: `function parseOpenMap(raw: string | null | undefined): OpenMap`
* `lib/fileTreeState.ts`: `function toggleOpen(map: OpenMap, id: string): OpenMap`
* `lib/fileTreeState.ts`: `const isFolderOpen`
* `lib/fileTreeTransform.ts`: `interface FileEntry`
* `lib/fileTreeTransform.ts`: `interface TreeNode`
* `lib/fileTreeTransform.ts`: `function buildFileTree(files: readonly FileEntry[]): TreeNode[]`
* `lib/fileTreeTransform.ts`: `function filesUnder(node: TreeNode): FileEntry[]`

## Dependencies
JavaScript (`deps.json`): `react`, `react-arborist`

## Stubs and what the host must provide
No stubs: every import resolves inside the module.

## Known limits
The wrapper is small; add icons and badges in your host.

## Quality
A (2 tests written for the pure parts)  
Tests copied: 1 (copied from the source, not run here).

## How to reuse
`buildFileTree(files)`, `<FileTree .../>`.
