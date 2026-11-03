// A status becomes a pill in ONE place. Pure data, no React, erasable TypeScript only (node --test imports it).
//
//   statusPill(domain, value) -> { kind, label, icon, detail?, dashed? }
//
// No component picks a colour: it renders the kind. Rules worth keeping when you replace the example map:
//   1. green (`pass`) only for a result that was actually produced, never for something unknown
//   2. an unknown value is `neutral` and shows its raw text, never green and never hidden
//   3. every pill has a word AND an icon, so colour is never the only signal

export type PillKind = "pass" | "fail" | "warn" | "info" | "neutral"

/** Icon names (kebab-case); components/ui/StatusPill.tsx maps each to its component. */
export type PillIcon = "check-circle-2" | "x-circle" | "alert-triangle" | "circle-dashed" | "clock" | "loader-2" | "help-circle" | "info"

export interface Pill {
  kind: PillKind
  label: string
  icon: PillIcon
  /** A second line: the reason, the date, the caveat. */
  detail?: string
  /** Hollow / dashed outline: not decided. */
  dashed?: boolean
}

export type PillDomain = "job" | "review"

// Example vocabulary. Replace with your own statuses.
const MAP: Record<PillDomain, Record<string, Pill>> = {
  job: {
    queued: { kind: "neutral", label: "Queued", icon: "clock", dashed: true },
    running: { kind: "info", label: "Running", icon: "loader-2" },
    done: { kind: "pass", label: "Done", icon: "check-circle-2" },
    failed: { kind: "fail", label: "Failed", icon: "x-circle" },
  },
  review: {
    approved: { kind: "pass", label: "Approved", icon: "check-circle-2" },
    rejected: { kind: "fail", label: "Rejected", icon: "x-circle" },
    pending: { kind: "warn", label: "Needs review", icon: "alert-triangle", dashed: true },
  },
}

export function statusPill(domain: PillDomain, value: string | null | undefined, detail?: string): Pill {
  const hit = MAP[domain]?.[String(value ?? "")]
  if (hit) return detail ? { ...hit, detail } : hit
  return { kind: "neutral", label: String(value ?? "Unknown") || "Unknown", icon: "help-circle", dashed: true, ...(detail ? { detail } : {}) }
}

/** True only for a pass; an unknown or neutral pill never counts as one. */
export const countsAsPass = (p: Pill): boolean => p.kind === "pass"
