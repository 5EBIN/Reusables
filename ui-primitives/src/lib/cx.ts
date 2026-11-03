// Class-name helper and the shared focus ring for the primitives in components/ui. Erasable TypeScript only.
export const cx = (...parts: Array<string | false | null | undefined>): string => parts.filter(Boolean).join(" ")

/** The keyboard focus ring: visible on keyboard focus only, 2px, the info colour (3:1 on every surface in both themes: checked by scripts/contrastCheck.mjs). */
export const FOCUS = "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-info"
