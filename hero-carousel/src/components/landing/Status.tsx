import { AlertTriangle, Check, Circle, Clock, Sparkles, X } from 'lucide-react';

/** Status is always colour + icon + word. Unknown is grey and never green. */
const KINDS = {
  pass: [Check, 'Pass'],
  fail: [X, 'Fail'],
  warn: [AlertTriangle, 'Needs review'],
  info: [Clock, 'Running'],
  ai: [Sparkles, 'Suggested'],
  neutral: [Circle, 'Unknown'],
} as const;

export type StatusKind = keyof typeof KINDS;

export function Status({ kind, label }: { kind: StatusKind; label?: string }) {
  const [Icon, text] = KINDS[kind];
  return (
    <span className={`st st-${kind}`}>
      <Icon className="i" aria-hidden="true" />
      {label ?? text}
    </span>
  );
}
