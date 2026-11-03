/**
 * Password strength scorer — NIST SP 800-63-4 aligned with practical UX.
 *
 * Scoring signals (0–100):
 *   Length           — biggest weight (up to 40 pts)
 *   Character variety — lowercase / uppercase / digit / special (10 pts each)
 *   Common password  — hard override → score = 0 regardless
 *   Repetition       — penalty for runs of the same char (−10)
 *
 * Strength tiers:
 *   Weak   0–24   — blocks form submission
 *   Fair  25–49   — minimum accepted
 *   Good  50–74   — recommended
 *   Strong 75–100 — excellent
 *
 * Why no zxcvbn? It's 400 KB. This gives 90% of the protection at 2 KB.
 */

// ─── Top-100 common / breached passwords (inline blocklist) ──────────────────
// Sources: HaveIBeenPwned top-100, SecLists common-credentials
const COMMON_PASSWORDS = new Set([
  'password','password1','password2','password123','passw0rd','pass',
  '123456','1234567','12345678','123456789','1234567890','12345','1234','123',
  'qwerty','qwerty123','qwerty1','qwertyuiop','qazwsx','qazwsxedc',
  'abc123','abcdef','abcd1234',
  'iloveyou','loveyou','iloveu',
  'letmein','letme1n',
  'monkey','dragon','master','shadow','sunshine','superman','batman','spiderman',
  'football','baseball','soccer','basketball','hockey',
  'welcome','hello','admin','login','test','guest','user','root',
  'trustno1','nothing','anything','something',
  'michael','ashley','jessica','charlie','andrew','daniel','matthew','thomas',
  'donald','thomas1','jordan','hunter','ranger','harley','dakota',
  '111111','000000','666666','999999','112233','121212','123123','654321',
  '1q2w3e4r','q1w2e3r4','1qaz2wsx',
  'changeme','change','default','secret','temp','temporary',
  'app','appai',                     // product-specific entries
])

// ─── Types ────────────────────────────────────────────────────────────────────
export type Strength = 'weak' | 'fair' | 'good' | 'strong'

export interface PasswordAnalysis {
  score:       number      // 0–100
  strength:    Strength
  isCommon:    boolean
  checks: {
    length:    boolean     // 8+
    lowercase: boolean
    uppercase: boolean
    digit:     boolean
    special:   boolean
    notCommon: boolean
  }
}

// ─── Scorer ───────────────────────────────────────────────────────────────────
export function analysePassword(pw: string): PasswordAnalysis {
  const len       = pw.length
  const hasLower  = /[a-z]/.test(pw)
  const hasUpper  = /[A-Z]/.test(pw)
  const hasDigit  = /[0-9]/.test(pw)
  const hasSpec   = /[^a-zA-Z0-9]/.test(pw)
  const isCommon  = COMMON_PASSWORDS.has(pw.toLowerCase())

  // Repetition penalty: any char repeated 4+ times consecutively
  const hasRun    = /(.)\1{3,}/.test(pw)

  // Length score: linear up to 16 chars → 40 pts max
  const lenScore = Math.min(len * 2.5, 40)

  // Variety score
  const varScore =
    (hasLower ? 10 : 0) +
    (hasUpper ? 10 : 0) +
    (hasDigit ? 10 : 0) +
    (hasSpec  ? 15 : 0)

  // Repetition penalty
  const repPenalty = hasRun ? 10 : 0

  let score = Math.round(lenScore + varScore - repPenalty)
  score = Math.max(0, Math.min(100, score))

  // Common password hard-override
  if (isCommon) score = 0

  const strength: Strength =
    score >= 75 ? 'strong' :
    score >= 50 ? 'good'   :
    score >= 25 ? 'fair'   : 'weak'

  return {
    score,
    strength,
    isCommon,
    checks: {
      length:    len >= 8,
      lowercase: hasLower,
      uppercase: hasUpper,
      digit:     hasDigit,
      special:   hasSpec,
      notCommon: !isCommon,
    },
  }
}

// ─── Minimum required to submit (signup / password reset) ─────────────────────
// Must be at least 'fair' AND not a common password.
export function isPasswordAcceptable(analysis: PasswordAnalysis): boolean {
  return analysis.strength !== 'weak' && !analysis.isCommon
}

// ─── Display meta ─────────────────────────────────────────────────────────────
export const STRENGTH_META: Record<Strength, { label: string; color: string; segments: number }> = {
  weak:   { label: 'Weak',   color: 'var(--fail)', segments: 1 },
  fair:   { label: 'Fair',   color: 'var(--warn)', segments: 2 },
  good:   { label: 'Good',   color: 'var(--info)', segments: 3 },
  strong: { label: 'Strong', color: 'var(--pass)', segments: 4 },
}
