// Light / dark: the choice, how it reaches <html>, and which Monaco theme goes with it. Pure data and functions, erasable TypeScript only (node --test imports it).
//
// The tokens live in styles/globals.css: `[data-theme="light"|"dark"]` on <html> forces one; no attribute follows the OS (prefers-color-scheme).
// The picker (Automatic / Light / Dark) arrives with Settings in R3; until then the mechanism is complete and the app starts in DEFAULT_PREF.
export type ThemePref = "auto" | "light" | "dark"
export type ResolvedTheme = "light" | "dark"

export const THEME_STORAGE_KEY = "app-theme"

/** What a visitor with no saved choice gets. "dark" until R4 has restyled every screen for light: the screens still hold dark-only colours, and "auto" would flip them for an OS in light mode. */
export const DEFAULT_PREF: ThemePref = "dark"

export function parsePref(raw: unknown): ThemePref {
  return raw === "light" || raw === "dark" || raw === "auto" ? raw : DEFAULT_PREF
}

/** The data-theme attribute for a choice; null = no attribute, the OS decides. */
export function attributeFor(pref: ThemePref): ResolvedTheme | null {
  return pref === "auto" ? null : pref
}

export function resolveTheme(pref: ThemePref, osDark: boolean): ResolvedTheme {
  return pref === "auto" ? (osDark ? "dark" : "light") : pref
}

/** Monaco's built-in themes: `vs` is light, `vs-dark` is dark. */
export function monacoThemeFor(theme: ResolvedTheme): "vs" | "vs-dark" {
  return theme === "dark" ? "vs-dark" : "vs"
}

/** Runs before the first paint so the page never flashes the wrong theme. It must stay in step with parsePref / attributeFor; the test runs this very string. */
export const THEME_BOOTSTRAP = `(function(){try{var p=localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)});if(p!=="light"&&p!=="dark"&&p!=="auto")p=${JSON.stringify(DEFAULT_PREF)};var r=document.documentElement;if(p==="auto")r.removeAttribute("data-theme");else r.setAttribute("data-theme",p)}catch(e){document.documentElement.setAttribute("data-theme",${JSON.stringify(DEFAULT_PREF)})}})()`
