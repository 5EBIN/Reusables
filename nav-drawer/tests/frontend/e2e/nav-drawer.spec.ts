// The signed-in sidebar below 1100 px: hidden, reachable through the menu button, and unchanged on a wide screen.
import { expect, test } from "@playwright/test";
import { ownerContext, signUpAndIn } from "./support/auth";

const SHOTS = process.env.NAV_SHOTS;                                     // optional folder for screenshots (a manual check, not an assertion)

test("the menu button opens the sidebar on narrow screens; the wide layout is unchanged", async ({ browser }) => {
  const ctx = await ownerContext(browser);
  await signUpAndIn(ctx, "Nav org");
  const page = await ctx.newPage();
  const shot = async (n: string) => { if (SHOTS) { await expect(page.locator(".hd")).toBeVisible(); await page.waitForTimeout(500); await page.screenshot({ path: `${SHOTS}/${n}.png` }); } };   // after the page and the slide have settled
  const menu = page.getByRole("button", { name: "Menu", exact: true });

  for (const w of [375, 960]) {
    await page.setViewportSize({ width: w, height: 800 });
    await page.goto("/overview");
    await expect(page.locator(".sb")).toBeHidden();
    await shot(`app-${w}-closed`);
    await menu.click();
    await expect(menu).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByRole("link", { name: "Surveys", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Overview", exact: true })).toBeFocused();
    await shot(`app-${w}-open`);
    await page.keyboard.press("Escape");
    await expect(page.locator(".sb")).toBeHidden();
    await expect(menu).toBeFocused();
  }
  await page.setViewportSize({ width: 375, height: 800 });
  await menu.click();
  await page.getByRole("link", { name: "Surveys", exact: true }).click();
  await expect(page).toHaveURL(/\/surveys/);
  await expect(page.locator(".sb")).toBeHidden();                        // closed after the link

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/overview");
  await expect(page.locator(".sb")).toBeVisible();
  await expect(menu).toBeHidden();
  await shot("app-1280");

  await page.setViewportSize({ width: 375, height: 800 });               // right to left: the sidebar comes in from the right
  await page.goto("/overview");
  await page.getByRole("button", { name: "عربي" }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.getByRole("button", { name: "القائمة", exact: true }).click();
  const box = await page.locator(".sb").boundingBox();
  expect(box!.x + box!.width).toBeGreaterThan(374);
  await expect(page.locator(".sb")).toBeVisible(); await expect(page.locator(".sb a.nav").first()).toBeVisible();
  await shot("app-375-rtl-open");
});
