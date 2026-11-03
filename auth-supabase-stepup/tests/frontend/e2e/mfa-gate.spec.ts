// A new administrator has a grace to set up two-step verification: they work at the first level, are reminded, and once the grace is over every page sends them to the two-step screen.
import { expect, test } from "@playwright/test";
import { endGrace, ownerContext, signUpFirstLevel } from "./support/auth";

test("a new administrator works during the grace with a banner and a dialog, and is sent to two-step once the grace is over", async ({ browser }) => {
  const ctx = await ownerContext(browser);
  const who = await signUpFirstLevel(ctx);
  const page = await ctx.newPage();
  await page.goto("/team");
  await expect(page).toHaveURL(/\/team$/);                                                                  // no forced set-up
  await expect(page.locator("[data-mfa-banner]")).toContainText("Two-step verification is required in 14 days");
  const dialog = page.getByRole("dialog", { name: "Protect your organisation with two-step verification" });
  await expect(dialog).toBeVisible();
  await page.getByRole("button", { name: "Remind me later" }).click();
  await expect(dialog).toBeHidden();
  await page.reload();
  await expect(page.locator("[data-mfa-banner]")).toBeVisible();                                          // the banner stays
  await expect(dialog).toBeHidden();                                                                       // the reminder is snoozed for a day

  endGrace(who.email);
  for (const path of ["/team", "/templates", "/surveys"]) {
    await page.goto(path);
    await expect(page).toHaveURL(/\/auth\?mfa=1/);
    await expect(page.locator("[data-panel=mfa]")).toBeVisible({ timeout: 20_000 });
  }
});
