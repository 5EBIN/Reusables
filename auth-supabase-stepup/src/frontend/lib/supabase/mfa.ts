import { createClient } from "./client";

export type MfaState = {
  enrolled: boolean;          // a verified authenticator-app factor exists
  factorId: string | null;
  aal2: boolean;              // this session already passed the second step
  needsVerify: boolean;       // enrolled, but this session has not passed it yet
};

/** Two-step verification is Supabase's TOTP: enrol, challenge and verify happen in the browser, and the session then carries `aal2`. */
export async function mfaState(): Promise<MfaState> {
  const sb = createClient();
  const [aal, factors] = await Promise.all([sb.auth.mfa.getAuthenticatorAssuranceLevel(), sb.auth.mfa.listFactors()]);
  const factor = factors.data?.totp?.[0] ?? null;                            // listFactors().totp holds verified factors only
  const cur = aal.data?.currentLevel, next = aal.data?.nextLevel;
  return { enrolled: !!factor, factorId: factor?.id ?? null, aal2: cur === "aal2", needsVerify: cur !== "aal2" && next === "aal2" };
}

/** Starts an enrolment: the QR code (an SVG data URI Supabase renders) and the key to type by hand. Half-finished enrolments are removed first. */
export async function startEnrol(name?: string): Promise<{ factorId: string; qr: string; secret: string } | null> {
  const sb = createClient();
  const all = await sb.auth.mfa.listFactors();
  for (const f of all.data?.all ?? []) if (f.factor_type === "totp" && f.status === "unverified") await sb.auth.mfa.unenroll({ factorId: f.id });
  const { data, error } = await sb.auth.mfa.enroll({ factorType: "totp", friendlyName: name?.trim() ? `${name.trim().slice(0, 40)} ${Date.now().toString(36)}` : `Authenticator ${Date.now()}` });
  if (error || !data) return null;
  return { factorId: data.id, qr: data.totp.qr_code, secret: data.totp.secret };
}

/** Challenge and verify in one step. On success the session is refreshed, so the next token carries aal2 and a fresh `totp` entry in `amr`. */
export async function verifyCode(factorId: string, code: string): Promise<boolean> {
  const { error } = await createClient().auth.mfa.challengeAndVerify({ factorId, code });
  return !error;
}

/** Turns two-step verification off (Supabase requires an aal2 session, so the caller verifies a code first). */
export async function removeFactor(factorId: string): Promise<boolean> {
  const { error } = await createClient().auth.mfa.unenroll({ factorId });
  return !error;
}

export type Factor = { id: string; name: string; createdAt: string };

/** The person's verified authenticator apps. The name they typed when adding one is shown without the suffix that keeps names unique. */
export async function verifiedFactors(): Promise<Factor[]> {
  const r = await createClient().auth.mfa.listFactors();
  return (r.data?.totp ?? []).map((f) => ({ id: f.id, name: (f.friendly_name ?? "").replace(/ [0-9a-z]{6,9}$/, "") || "Authenticator", createdAt: f.created_at }));
}
