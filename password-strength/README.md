# password-strength

**Category:** frontend-lib  
**Origin:** extracted from a production Next.js/FastAPI app.

## What it does
Password analysis with a strength meter and a password field.

## Problem it solved
Consistent feedback on password choice.

## Public interface
* `components/auth/PasswordField.tsx`: `function PasswordField(`
* `components/auth/PasswordStrength.tsx`: `function PasswordStrength(`
* `lib/passwordStrength.ts`: `type Strength`
* `lib/passwordStrength.ts`: `interface PasswordAnalysis`
* `lib/passwordStrength.ts`: `function analysePassword(pw: string): PasswordAnalysis`
* `lib/passwordStrength.ts`: `function isPasswordAcceptable(analysis: PasswordAnalysis): boolean`
* `lib/passwordStrength.ts`: `const STRENGTH_META: Record<Strength,`

## Dependencies
JavaScript (`deps.json`): `lucide-react`, `react`

## Stubs and what the host must provide
No stubs: every import resolves inside the module.

## Known limits
Heuristic, not a breach-list check.

## Quality
B  
Tests copied: 0 (copied from the source, not run here).

## How to reuse
`analyse(password)`.
