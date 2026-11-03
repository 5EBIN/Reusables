// R2: light / dark. lib/theme.ts (the choice, the attribute, Monaco's theme, the before-first-paint script) and lib/tagInput.ts.
//   node --test tests/theme.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";

await import("./support/alias.mjs");
const { parsePref, attributeFor, resolveTheme, monacoThemeFor, DEFAULT_PREF, THEME_BOOTSTRAP, THEME_STORAGE_KEY } = await import("../src/lib/theme.ts");
const { addTag } = await import("../src/lib/tagInput.ts");

test("a saved choice is read back; anything else is the default", () => {
  for (const v of ["auto", "light", "dark"]) assert.equal(parsePref(v), v);
  for (const v of [null, undefined, "", "Dark", "blue", 1, {}]) assert.equal(parsePref(v), DEFAULT_PREF);
});

test("until R4 the default is dark, so no screen flips with the OS setting", () => {
  assert.equal(DEFAULT_PREF, "dark");
});

test("Automatic puts no attribute on <html> (the OS decides); Light and Dark force theirs", () => {
  assert.deepEqual(["auto", "light", "dark"].map(attributeFor), [null, "light", "dark"]);
  assert.deepEqual([resolveTheme("auto", true), resolveTheme("auto", false), resolveTheme("light", true), resolveTheme("dark", false)], ["dark", "light", "light", "dark"]);
});

test("Monaco: vs in light, vs-dark in dark", () => {
  assert.equal(monacoThemeFor("light"), "vs");
  assert.equal(monacoThemeFor("dark"), "vs-dark");
  assert.equal(monacoThemeFor(resolveTheme("auto", true)), "vs-dark");
  assert.equal(monacoThemeFor(resolveTheme("auto", false)), "vs");
});

/** Runs the real bootstrap string against a fake document and storage. */
function boot(stored, { throws = false } = {}) {
  const attrs = {};
  const document = { documentElement: { setAttribute: (k, v) => (attrs[k] = v), removeAttribute: (k) => delete attrs[k] } };
  const localStorage = { getItem: (k) => { if (throws) throw new Error("blocked"); return k === THEME_STORAGE_KEY ? stored : null; } };
  new Function("document", "localStorage", THEME_BOOTSTRAP)(document, localStorage);
  return attrs["data-theme"];
}

test("the before-paint script applies the saved choice, and the default when there is none, junk, or storage is blocked", () => {
  assert.equal(boot("light"), "light");
  assert.equal(boot("dark"), "dark");
  assert.equal(boot("auto"), undefined, "Automatic leaves the attribute off");
  assert.equal(boot(null), "dark");
  assert.equal(boot("purple"), "dark");
  assert.equal(boot(null, { throws: true }), "dark");
});

test("the script agrees with parsePref / attributeFor for every stored value", () => {
  for (const v of ["auto", "light", "dark", null, "x"]) assert.equal(boot(v) ?? null, attributeFor(parsePref(v)), String(v));
});

test("TagInput: trims, ignores empty and repeated (any case), and returns the same list when nothing was added", () => {
  const base = ["Admin"];
  assert.deepEqual(addTag(base, "  Customer "), ["Admin", "Customer"]);
  assert.deepEqual(addTag(base, "Customer,"), ["Admin", "Customer"]);
  for (const raw of ["", "   ", ",", "admin", " ADMIN "]) assert.equal(addTag(base, raw), base, JSON.stringify(raw));
  assert.deepEqual(base, ["Admin"], "the input list is not changed");
});
