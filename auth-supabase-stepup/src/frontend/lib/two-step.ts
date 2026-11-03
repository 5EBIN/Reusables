/** Roles that must pass two-step verification in every organisation (the same fixed set as the API's ALWAYS_MFA_ROLES). The proxy uses this on the role cookie as a hint to skip
 *  a wasted render; the API stays the authority (an organisation can add roles, which the shell finds out from GET /v1/me). */
export const TWO_STEP_ROLES = ["client_admin", "super_admin", "consultant"] as const;
export const needsTwoStep = (role: string | undefined): boolean => !!role && (TWO_STEP_ROLES as readonly string[]).includes(role);

/** The proxy's early answer for a request at the first sign-in level: send it to the second step only when the hint cookie `sv_mfa` (written by the page from GET /v1/me) says the
 *  person is enrolled (they are always challenged) or that the grace is over. No hint, or a grace still running: let it through; the shell asks the API and redirects if it must. */
export function mustChallenge(role: string | undefined, hint: string | undefined, nowMs = Date.now()): boolean {
  if (!needsTwoStep(role) || !hint) return false;
  if (hint === "enrolled" || hint === "expired") return true;
  if (hint.startsWith("grace:")) { const end = Number(hint.slice(6)); return Number.isFinite(end) && end * 1000 <= nowMs; }
  return false;
}

/** Forget the proxy's two-step hint. It describes whoever used this browser last, so sign-in and sign-out drop it (a stale "enrolled" or "expired" would send the next person at the first
 *  sign-in level back to the sign-in page before any page could write a fresh one). The next page that loads GET /v1/me writes it again. */
export function forgetTwoStepHint(): void {
  try { document.cookie = "sv_mfa=; path=/; max-age=0; samesite=lax"; } catch { /* a hint only */ }
}
