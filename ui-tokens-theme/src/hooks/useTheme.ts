'use client'

import { useCallback, useSyncExternalStore } from 'react'
import { attributeFor, monacoThemeFor, parsePref, resolveTheme, THEME_STORAGE_KEY, type ResolvedTheme, type ThemePref } from '@/lib/theme'

const listeners = new Set<() => void>()
const notify = () => listeners.forEach(l => l())

function readPref(): ThemePref {
  try { return parsePref(localStorage.getItem(THEME_STORAGE_KEY)) } catch { return parsePref(null) }
}
const osDark = () => typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches

function subscribe(cb: () => void) {
  listeners.add(cb)
  const mq = typeof matchMedia === 'function' ? matchMedia('(prefers-color-scheme: dark)') : null
  mq?.addEventListener('change', cb)
  window.addEventListener('storage', cb)
  return () => { listeners.delete(cb); mq?.removeEventListener('change', cb); window.removeEventListener('storage', cb) }
}

/** The saved choice, the theme it resolves to right now, the Monaco theme to match, and a setter that saves and applies. */
export function useTheme() {
  const pref = useSyncExternalStore(subscribe, readPref, () => parsePref(null))
  const dark = useSyncExternalStore(subscribe, osDark, () => false)
  const resolved: ResolvedTheme = resolveTheme(pref, dark)
  const setPref = useCallback((next: ThemePref) => {
    try { localStorage.setItem(THEME_STORAGE_KEY, next) } catch { /* private window: applies for this page only */ }
    const attr = attributeFor(next)
    if (attr) document.documentElement.setAttribute('data-theme', attr)
    else document.documentElement.removeAttribute('data-theme')
    notify()
  }, [])
  return { pref, resolved, monacoTheme: monacoThemeFor(resolved), setPref }
}
