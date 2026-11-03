# visual-editor-wrapper

**Category:** frontend-lib  
**Origin:** extracted from a production Next.js/FastAPI app.

## What it does
A GrapesJS wrapper: canvas, left/right panels, token panel, floating property panel, block definitions, an element-properties hook, and a static guard test that forbids unsafe iframe sandboxes.

## Problem it solved
Embedding a visual HTML editor safely.

## Public interface
* `components/design-editor/DesignCanvas.tsx`: `interface BlockDelta`
* `components/design-editor/DesignCanvas.tsx`: `interface MoveDelta`
* `components/design-editor/DesignCanvas.tsx`: `function DesignCanvas(`
* `components/design-editor/DesignTokenPanel.tsx`: `function DesignTokenPanel(`
* `components/design-editor/FloatingPropertyPanel.tsx`: `interface StyleChange`
* `components/design-editor/FloatingPropertyPanel.tsx`: `function FloatingPropertyPanel(`
* `components/design-editor/GrapesCanvas.tsx`: `function safeGetHtml(editor: Editor): string`
* `components/design-editor/GrapesCanvas.tsx`: `function GrapesCanvas(`
* `components/design-editor/GrapesEditor.tsx`: `function GrapesEditor(`
* `components/design-editor/LeftSidebar.tsx`: `function LeftSidebar(`
* `components/design-editor/PageList.tsx`: `function PageList(`
* `components/design-editor/RightSidebar.tsx`: `function RightSidebar(`
* `components/design-editor/TopToolbar.tsx`: `function TopToolbar(`
* `components/design-editor/blockDefs.ts`: `interface BlockDef`
* `components/design-editor/blockDefs.ts`: `const BLOCKS: BlockDef[]`
* `components/design-editor/blockDefs.ts`: `const CATEGORIES`
* `hooks/useElementProperties.ts`: `type ElementType`
* `hooks/useElementProperties.ts`: `interface ElementProperties`
* `hooks/useElementProperties.ts`: `function detectElementType(tagName: string): ElementType`
* `hooks/useElementProperties.ts`: `function useElementProperties()`

## Dependencies
JavaScript (`deps.json`): `clsx`, `grapesjs`, `grapesjs-blocks-basic`, `grapesjs-plugin-forms`, `grapesjs-preset-webpage`, `lucide-react`, `react`

## Stubs and what the host must provide
`src/app/_stubs.py` / `src/_stubs.ts` keep imports resolvable. The host must replace: `DesignToken`, `PageDesign`.

## Known limits
Host types (`DesignToken`, `PageDesign`) are stubs. The preview/autosave drawer was not separable and is not included; the original demo page template was moved out as it carried a brand.

## Quality
C (1 guard test; components untested)  
Tests copied: 1 (copied from the source, not run here).

## How to reuse
Mount `GrapesEditor` and supply tokens.

(Stub signatures were derived from the host code they stand for; they carry no behaviour.)
