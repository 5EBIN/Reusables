// The sign-in journey against a local Supabase (`supabase start` in backend/): sign up -> confirm from the mail catcher -> log in -> a dashboard loaded through
// Next.js -> FastAPI -> log out. Needs the web app on :3100 built with the local project's NEXT_PUBLIC_SUPABASE_URL / _PUBLISHABLE_KEY, a running backend
// with SUPABASE_URL set to the same project, and the mail catcher on :55324.
import { expect, test } from "@playwright/test";
import { completeMfa, endGrace, mailTo, newEmail, PASSWORD, tokenHash } from "./support/auth";

// `next start` builds redirects on localhost, so the whole journey runs on that host (the session cookie is per host).
test.use({ baseURL: "http://localhost:3100" });

test("sign up, confirm by email, sign in, load a dashboard, sign out", async ({ page }) => {
  const email = newEmail("flow");
  await page.goto("/auth");
  await page.locator('[data-tab=register]').click();
  const reg = page.locator("[data-panel=register]");
  const inputs = reg.locator("input.in");
  await inputs.nth(0).fill("Jordan"); await inputs.nth(1).fill("Lee"); await inputs.nth(2).fill(email); await inputs.nth(3).fill(PASSWORD);
  await reg.locator("input[type=checkbox]").check();
  await reg.locator("button.btn.pri").click();

  await expect(page.locator("[data-panel=verify]")).toContainText(email);                       // "We sent a confirmation link to <address>"
  const hash = tokenHash(await mailTo(page.request, email));
  expect(hash).not.toBe("");
  await page.goto(`/auth/confirm?token_hash=${hash}&type=signup&next=${encodeURIComponent("/auth?welcome=1")}`);   // the link in the email signs the user in
  await page.getByLabel("Organisation name").fill("Flow org");
  await page.getByText("Create organisation").click();
  await expect(page).toHaveURL(/\/overview$/);                                                    // the creator is an administrator with a grace: the dashboard, with the reminder
  await expect(page.locator("[data-mfa-banner]")).toBeVisible();
  endGrace(email);                                                                              // the grace is days long: end it here to go through the real set-up
  await page.goto("/surveys");
  await expect(page).toHaveURL(/\/auth\?mfa=1/);
  const key = await completeMfa(page);

  await page.goto("/surveys");                                    // browser -> Next.js -> FastAPI with the user's bearer (now aal2)
  await expect(page.locator("h1")).toHaveText("Surveys");

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/auth$/);
  await page.goto("/surveys");
  await expect(page).toHaveURL(/\/auth\?next=%2Fsurveys$/);        // the session is gone

  await page.locator("[data-panel=signin] input.in").nth(0).fill(email);
  await page.locator("[data-panel=signin] input.in").nth(1).fill(PASSWORD);
  await page.locator("[data-panel=signin] button.btn.pri").click();
  await expect(page.locator("[data-panel=mfa]")).toBeVisible();   // sign in -> two-step challenge -> dashboard; enrolled now: the password alone is not enough
  await completeMfa(page, key);
  await expect(page).toHaveURL(/\/surveys$/);
});
