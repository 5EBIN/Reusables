# ui-tokens-theme

**Category:** ui-kit  
**Origin:** extracted from a production Next.js/FastAPI app.

## What it does
Dark/light design tokens as CSS variables, Tailwind colour mapping, theme preference/resolution (auto/light/dark, Monaco theme, before-first-paint script), tag-input helper, and a WCAG contrast checker that fails on low-contrast token pairs.

## Problem it solved
Colours were scattered and contrast was unchecked.

## Public interface
* `hooks/useTheme.ts`: `function useTheme()`
* `lib/tagInput.ts`: `function addTag(list: string[], raw: string): string[]`
* `lib/theme.ts`: `type ThemePref`
* `lib/theme.ts`: `type ResolvedTheme`
* `lib/theme.ts`: `const THEME_STORAGE_KEY`
* `lib/theme.ts`: `const DEFAULT_PREF: ThemePref`
* `lib/theme.ts`: `function parsePref(raw: unknown): ThemePref`
* `lib/theme.ts`: `function attributeFor(pref: ThemePref): ResolvedTheme | null`
* `lib/theme.ts`: `function resolveTheme(pref: ThemePref, osDark: boolean): ResolvedTheme`
* `lib/theme.ts`: `function monacoThemeFor(theme: ResolvedTheme): "vs" | "vs-dark"`
* `lib/theme.ts`: `const THEME_BOOTSTRAP`

## Dependencies
JavaScript (`deps.json`): `react`

## Stubs and what the host must provide
No stubs: every import resolves inside the module.

## Known limits
Token names are ours; rename to taste.

## Quality
A (tests copied for tokens and theme)  
Tests copied: 4 (copied from the source, not run here).

## How to reuse
Copy `globals.css`, `tailwind.config.js`, run `node scripts/contrastCheck.mjs`.
