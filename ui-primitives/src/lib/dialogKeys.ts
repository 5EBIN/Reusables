// What Esc and a click on the backdrop do to a dialog. A dialog that waits for a decision is BLOCKING: neither closes it, it closes only through its own buttons. One rule for every dialog
// (components/ui/Dialog.tsx), so the plan popups cannot differ from the rest. Pure data, erasable TypeScript only (node --test imports it).

export type DismissAction = "close" | "ignore"

/** Esc: closes a dialog, unless a decision is pending. */
export const escapeAction = (blocking: boolean): DismissAction => (blocking ? "ignore" : "close")

/** A click on the backdrop (outside the panel): the same rule. */
export const backdropAction = (blocking: boolean): DismissAction => (blocking ? "ignore" : "close")
