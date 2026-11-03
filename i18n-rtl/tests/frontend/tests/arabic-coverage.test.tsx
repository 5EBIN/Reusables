// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { I18nProvider } from "../components/I18n";
import { decode, enc, stripMarks, useDecode } from "../lib/decode";
import { dayMonth, dayMonthEnc, dayMonthL, relTime, relTimeEnc, relTimeL } from "../lib/format";
import { shortDateEnc, whenLabelEnc } from "../lib/people";

afterEach(cleanup);
const NOW = new Date("2026-10-07T12:00:00Z");
const ago = (s: number) => new Date(NOW.getTime() - s * 1000).toISOString();

describe("relative times and dates are translatable (they used to be English-only)", () => {
  const cases: [number, string, string, string][] = [
    [20, "Just now", "الآن", "ابھی"],
    [5 * 60, "5 min ago", "قبل 5 د", "5 منٹ پہلے"],
    [3 * 3600, "3 h ago", "قبل 3 س", "3 گھنٹے پہلے"],
    [30 * 3600, "Yesterday", "أمس", "کل"],
    [4 * 86400, "4 days ago", "قبل 4 أيام", "4 دن پہلے"],
  ];
  it.each(cases)("%s s ago", (s, en, ar, ur) => {
    expect(relTime(ago(s), NOW)).toBe(en);                       // the English helper is unchanged
    expect(decode("en", relTimeEnc(ago(s), NOW))).toBe(en);
    expect(decode("ar", relTimeEnc(ago(s), NOW))).toBe(ar);
    expect(decode("ur", relTimeEnc(ago(s), NOW))).toBe(ur);
    expect(relTimeL("ar", ago(s), NOW)).toBe(ar);
    expect(decode("xx", relTimeEnc(ago(s), NOW))).toBe(en);      // unknown language: English, never a key
  });
  it("older dates become '12 Sep' in the reader's language, with month names for every language", () => {
    const iso = "2026-09-12T08:00:00Z";
    expect(dayMonth(iso)).toBe("12 Sep");
    expect(decode("en", dayMonthEnc(iso))).toBe("12 Sep");
    expect(decode("ar", dayMonthEnc(iso))).toBe("12 سبتمبر");
    expect(decode("ar", relTimeEnc(iso, NOW))).toBe("12 سبتمبر");
    expect(dayMonthL("ru", iso)).toBe("12 сент."); expect(dayMonthL("hi", iso)).toBe("12 सितंबर"); expect(dayMonthL("fil", iso)).toBe("12 Set"); expect(dayMonthL("ur", iso)).toBe("12 ستمبر");
  });
  it("garbage dates render a dash in every language", () => {
    for (const f of [relTimeEnc, dayMonthEnc]) expect(f("not a date")).toBe("—");
    expect(relTimeL("ar", "x")).toBe("—"); expect(dayMonthL("ar", "x")).toBe("—");
  });
  it("API text can never select a message: a marker inside user content is stripped, and unknown keys render as plain text", () => {
    const hostile = stripMarks({ title: `${enc("rel_now")}hello` });
    expect(decode("ar", hostile.title)).toBe("rel_nowhello".replace("rel_nowhello", hostile.title));
    expect(decode("ar", "\u0001nope|x")).toBe("nope|x");
    expect(decode("ar", "plain text")).toBe("plain text");
  });
});

describe("nested messages", () => {
  it("a message may carry another message as an argument (Proposed by X · <relative time>) and both are translated", () => {
    const m = enc("ap_proposed_by", "Taylor Kim", relTimeEnc(ago(2 * 3600), NOW));
    expect(decode("en", m)).toBe("Proposed by Taylor Kim · 2 h ago");
    expect(decode("ar", m)).toContain("قبل 2 س");
    expect(decode("ur", m)).toContain("2 گھنٹے پہلے");
  });
  it("approvals and team dates/times (Today 10:00, 12 Oct) are translated too", () => {
    const t = (iso: string) => whenLabelEnc(iso, NOW);
    expect(decode("en", t("2026-10-07T06:00:00Z"))).toBe("Today 10:00");
    expect(decode("ar", t("2026-10-07T06:00:00Z"))).toBe("اليوم 10:00");
    expect(decode("ar", t("2026-10-06T06:00:00Z"))).toBe("أمس 10:00");
    expect(decode("ar", t("2026-10-08T06:00:00Z"))).toBe("غدًا 10:00");
    expect(decode("ar", t("2026-09-03T11:30:00Z"))).toBe("3 سبتمبر 15:30");
    expect(decode("ru", t("2026-10-08T06:00:00Z"))).toBe("Завтра, 10:00");
    expect(decode("en", shortDateEnc("2026-10-12T00:00:00Z", NOW))).toBe("12 Oct");
    expect(decode("ar", shortDateEnc("2027-01-05T00:00:00Z", NOW))).toBe("5 يناير 2027");
    expect(t(null as never)).toBe("—"); expect(shortDateEnc("nope")).toBe("—");
  });
  it("renders through the useDecode hook in a provider", () => {
    function Probe({ v }: { v: string }) { const m = useDecode(); return <p data-testid="p">{m(v)}</p>; }
    render(<I18nProvider initial="ar"><Probe v={relTimeEnc(ago(3 * 86400), NOW)} /></I18nProvider>);
    expect(screen.getByTestId("p").textContent).toBe("قبل 3 أيام");
  });
});
