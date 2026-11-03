import { expect, type APIRequestContext, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { totp } from "./totp";

// Local Supabase (`supabase start` in backend/): Auth on 55321, the mail catcher on 55324. The app under test must be built with the matching
// NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY.
const SUPABASE = process.env.E2E_SUPABASE_URL ?? "http://127.0.0.1:55321";
const MAIL = process.env.E2E_MAIL_URL ?? "http://127.0.0.1:55324";
const KEY = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? process.env.E2E_SUPABASE_KEY ?? "";
export const csrf = { "x-sv-csrf": "1" };
export const PASSWORD = "a long enough passphrase 123";

export const newEmail = (p = "e2e") => `${p}${randomUUID().slice(0, 8)}@example.com`;

/** The newest email to `to` in the local mail catcher, polled until it arrives. */
export async function mailTo(request: APIRequestContext, to: string): Promise<{ text: string; html: string }> {
  for (let i = 0; i < 40; i++) {
    const found = await (await request.get(`${MAIL}/api/v1/search?query=${encodeURIComponent(`to:${to}`)}`)).json().catch(() => null);
    const id = found?.messages?.[0]?.ID;
    if (id) { const m = await (await request.get(`${MAIL}/api/v1/message/${id}`)).json(); return { text: m.Text ?? "", html: m.HTML ?? "" }; }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`no email for ${to}`);
}

export const tokenHash = (mail: { text: string; html: string }) => /token_hash=([\w-]+)/.exec(mail.html + mail.text)?.[1] ?? "";
export const code = (mail: { text: string }) => /\b(\d{6})\b/.exec(mail.text)?.[1] ?? "";

export const BASE = "http://127.0.0.1:3100";

/** A fresh browser context for a signed-in owner (the config's baseURL does not reach contexts a spec creates itself). */
export const ownerContext = (browser: Browser) => browser.newContext({ baseURL: BASE });

const lastCode = new Map<string, string>();         // a code is good once: a second step-up inside the same 30 seconds waits for the next one

/** The two-step page (`/auth?mfa=1`): set up (the page shows the key; read it) or verify (pass the key from the set-up), type the authenticator code, confirm. Returns the key. */
export async function completeMfa(page: Page, knownKey?: string) {
  const key = knownKey ?? (await page.locator("[data-panel=mfa] code.mono").first().textContent({ timeout: 20_000 }))?.trim() ?? "";
  expect(key).not.toBe("");
  let digits = totp(key);
  for (let i = 0; i < 35 && lastCode.get(key) === digits; i++) { await page.waitForTimeout(1000); digits = totp(key); }
  lastCode.set(key, digits);
  const boxes = page.locator("[data-panel=mfa] input.in");
  for (let i = 0; i < 6; i++) await boxes.nth(i).fill(digits[i]);
  await page.locator("[data-panel=mfa] button.btn.pri").click();
  await expect(page).not.toHaveURL(/\/auth/, { timeout: 20_000 });
  return key;
}

/** Sign up with Supabase Auth, confirm through the emailed /auth/confirm link (which signs this context in) and create an organisation: an administrator at the first level (aal1), no two-step set up yet. */
export async function signUpFirstLevel(ctx: BrowserContext, orgName = "E2E org") {
  const request: APIRequestContext = ctx.request;
  const email = newEmail();
  const r = await request.post(`${SUPABASE}/auth/v1/signup`, { headers: { apikey: KEY }, data: { email, password: PASSWORD } });
  expect(r.ok()).toBeTruthy();
  const hash = tokenHash(await mailTo(request, email));
  expect(hash).not.toBe("");
  expect((await request.get(`${BASE}/auth/confirm?token_hash=${hash}&type=signup&next=${encodeURIComponent("/overview")}`)).ok()).toBeTruthy();       // sets the session cookies on this context
  expect((await request.post(`${BASE}/api/org`, { data: { name: orgName }, headers: csrf })).status()).toBe(201);
  return { email, password: PASSWORD };
}

/** Ends the two-step grace of one person at once (the grace is days long; the database is moved, not the clock). */
export function endGrace(email: string) {
  sql(`update memberships set mfa_grace_until = now() - interval '1 day' where user_id in (select id from users where email = '${email}')`);
}

/** The same, with the grace ended and the real two-step page gone through: the context ends up with a session that has passed it (aal2). */
export async function signUpAndIn(ctx: BrowserContext, orgName = "E2E org") {
  const who = await signUpFirstLevel(ctx, orgName);
  endGrace(who.email);                                                            // a new administrator has days to set it up; these specs go through the set-up now
  const page = await ctx.newPage();
  await page.goto(`${BASE}/auth?mfa=1`);
  await completeMfa(page);
  await page.close();
  return who;
}

/** One SQL statement against the database the API uses, for what the API deliberately cannot do (the embed spec lists an http origin, which production refuses).
 *  E2E_PSQL is the command that runs psql as a superuser on that database, e.g. `docker exec -i supabase_db_survey_backend psql -U postgres -d app_test -qc`. */
export function sql(statement: string) {
  if (!process.env.E2E_PSQL) return void execFileSync("su", ["postgres", "-c", `psql ${process.env.SV_DB ?? "app"} -qc "${statement}"`]);
  const cmd = process.env.E2E_PSQL.split(" ");
  execFileSync(cmd[0], [...cmd.slice(1), statement]);
}
