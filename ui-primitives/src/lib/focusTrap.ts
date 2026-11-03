// Tab order inside a modal dialog. Pure; `.ts` imports so `node --test` can import it.

/** Where Tab (or Shift+Tab) goes next among `count` focusable elements, wrapping at both ends. `current` is the index of the focused one, or -1 when focus is outside the list. -1 = nothing to focus. */
export function nextFocusIndex(current: number, count: number, backwards: boolean): number {
  if (count <= 0) return -1
  if (current < 0) return backwards ? count - 1 : 0
  return backwards ? (current - 1 + count) % count : (current + 1) % count
}
