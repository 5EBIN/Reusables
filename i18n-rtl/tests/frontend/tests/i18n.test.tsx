// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { I18nProvider } from "../components/I18n";
import { T } from "../components/T";
import { dictionary } from "../lib/dictionary";
import { CATALOG_AR, CATALOG_EN } from "../lib/i18n/catalog";
import { pageLeaves } from "../lib/i18n/leaves";
import { LOCALES, LOCALE_CODES, TABLE_IDS } from "../lib/i18n/locales";
import { RTL, LANGS } from "../lib/lang";
import { format } from "../lib/messages";
import { rformat } from "../lib/messages-reports";
import { formatD } from "../lib/msg-d";
import { aformat } from "../lib/authoring-messages";
import { rt } from "../lib/runner/strings";
import { P } from "../components/interview/strings";

afterEach(cleanup);
const vars = (s: string) => [...s.matchAll(/\{([A-Za-z0-9_]+)\}/g)].map((m) => m[1]).sort();
const leaves = pageLeaves();

describe("interface strings exist for every language (machine-drafted, see docs/I18N.md)", () => {
  it("reads the page leaves of the generated pages", () => {
    expect(leaves.length).toBeGreaterThanOrEqual(24);
    expect(leaves.map((l) => l.en)).toContain("Overview");
  });

  for (const code of LOCALE_CODES) {
    describe(code, () => {
      it("has a translation for every <T> page leaf, and none is empty", () => {
        for (const { en } of leaves) {
          const v = LOCALES[code].t[en];
          expect(v, `${code}: page text "${en}"`).toBeTruthy();
          expect(v.trim().length).toBeGreaterThan(0);
        }
        expect(Object.keys(LOCALES[code].t).sort()).toEqual(leaves.map((l) => l.en).sort());     // no stale entries
      });
      for (const id of TABLE_IDS) {
        it(`table "${id}": every key present, no empty value, no stale key, placeholders preserved`, () => {
          const en = CATALOG_EN[id], tr = LOCALES[code].msgs[id];
          const missing = Object.keys(en).filter((k) => !(k in tr));
          expect(missing, `${code}/${id} is missing keys`).toEqual([]);
          const stale = Object.keys(tr).filter((k) => !(k in en));
          expect(stale, `${code}/${id} has keys that are not in English`).toEqual([]);
          for (const [k, v] of Object.entries(tr)) {
            expect(typeof v === "string" && v.trim().length > 0, `${code}/${id}/${k} is empty`).toBe(true);
            expect(vars(v), `${code}/${id}/${k} placeholders`).toEqual(vars(en[k]));
          }
        });
      }
    });
  }

  it("the dictionary the T component reads is the locale page text", () => {
    for (const code of LOCALE_CODES) expect(dictionary[code]).toBe(LOCALES[code].t);
  });

  it("Arabic still covers every key of every table that has an Arabic table (the other languages are measured against English)", () => {
    for (const id of TABLE_IDS) {
      if (id === "runner" || id === "interview") continue;
      const missing = Object.keys(CATALOG_EN[id]).filter((k) => !(k in CATALOG_AR[id]));
      expect(missing, `ar/${id}`).toEqual([]);
    }
  });
});

describe("lookup falls back safely", () => {
  it("each language reads its own table; English is the fallback for unknown languages", () => {
    expect(format("ur", "retry")).toBe(LOCALES.ur.msgs.messages.retry);
    expect(format("hi", "retry")).toBe(LOCALES.hi.msgs.messages.retry);
    expect(format("ru", "retry")).toBe(LOCALES.ru.msgs.messages.retry);
    expect(format("fil", "retry")).toBe(LOCALES.fil.msgs.messages.retry);
    expect(format("ar", "retry")).not.toBe(format("en", "retry"));
    expect(format("xx", "retry")).toBe("Try again");
    expect(format("ur", "retry")).not.toBe(format("ar", "retry"));          // Urdu no longer shows Arabic text
  });
  it("placeholders are substituted in every language and every table", () => {
    for (const l of ["ur", "hi", "ru", "fil"]) {
      expect(format(l, "locked", { s: 7 })).toContain("7");
      expect(rformat(l, "frozen", { v: 3 })).toContain("3");
      expect(formatD(l, "pair_expires", { m: 15 })).toContain("15");
      expect(aformat(l, "new_draft", { n: 4 })).toContain("4");
      expect(rt(l, "question_of", { a: 2, n: 9 })).toMatch(/2.*9/);
      expect(P(l, "topic", { a: 1, b: 5 })).toMatch(/1.*5/);
    }
  });
  it("a missing key in a language falls back to English rather than showing a key or nothing", () => {
    const saved = LOCALES.hi.msgs.messages.retry;
    delete LOCALES.hi.msgs.messages.retry;
    try { expect(format("hi", "retry")).toBe("Try again"); } finally { LOCALES.hi.msgs.messages.retry = saved; }
  });
});

describe("right-to-left and <T>", () => {
  it("Urdu is RTL, English/Hindi/Russian/Filipino are LTR", () => {
    expect([...RTL].sort()).toEqual(["ar", "ur"]);
    for (const l of LANGS) expect(RTL.has(l)).toBe(["ar", "ur"].includes(l));
  });
  it("the provider sets lang and dir=rtl on the document for Urdu and dir=ltr for the others", () => {
    for (const [l, dir] of [["ur", "rtl"], ["ar", "rtl"], ["hi", "ltr"], ["ru", "ltr"], ["fil", "ltr"], ["en", "ltr"]] as const) {
      cleanup();
      render(<I18nProvider initial={l} dict={dictionary}><span /></I18nProvider>);
      expect(document.documentElement.lang).toBe(l);
      expect(document.documentElement.dir).toBe(dir);
    }
  });
  it("<T> renders the Urdu, Hindi, Russian and Filipino text, Arabic from the mockup, and English as the fallback", () => {
    const row = (l: "en" | "ar" | "ur" | "hi" | "ru" | "fil") => { cleanup(); render(<I18nProvider initial={l} dict={dictionary}><p data-testid="t"><T ar="نظرة عامة">Overview</T> | <T ar="س">Not in any dictionary</T></p></I18nProvider>); return screen.getByTestId("t").textContent; };
    expect(row("en")).toBe("Overview | Not in any dictionary");
    expect(row("ar")).toBe("نظرة عامة | س");
    expect(row("ur")).toBe("جائزہ | Not in any dictionary");
    expect(row("hi")).toBe("अवलोकन | Not in any dictionary");
    expect(row("ru")).toBe("Обзор | Not in any dictionary");
    expect(row("fil")).toBe("Pangkalahatang-tanaw | Not in any dictionary");
  });
  it("Urdu strings are written in the Arabic script, Hindi in Devanagari, Russian in Cyrillic", () => {
    const sample = (c: "ur" | "hi" | "ru") => Object.values(LOCALES[c].msgs.messages).join(" ");
    expect(sample("ur")).toMatch(/[؀-ۿ]/); expect(sample("ur")).not.toMatch(/[ऀ-ॿ]/);
    expect(sample("hi")).toMatch(/[ऀ-ॿ]/);
    expect(sample("ru")).toMatch(/[Ѐ-ӿ]/);
  });
});
