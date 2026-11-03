// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MfaGate, daysLeft, hintValue, type Nudge } from "../components/MfaGate";
import { I18nProvider } from "../components/I18n";
import { nav } from "./setup";
import { server, useMsw } from "./msw";

useMsw();
afterEach(cleanup);
beforeEach(() => { document.cookie = "sv_mfa=; max-age=0; path=/"; sessionStorage.clear(); nav.pathname = "/overview"; });
const NOW = Date.now();
const inDays = (d: number) => new Date(NOW + d * 86_400_000 - 3_600_000).toISOString();           // an hour short of d days: the nearest day is d
const nudge = (over: Partial<Nudge> = {}): Nudge => ({ required: true, enrolled: false, graceEndsAt: inDays(10), snoozedUntil: null, ...over });
const mount = (n: Nudge, lang: "en" | "ar" = "en") => render(<I18nProvider initial={lang}><MfaGate nudge={n} /></I18nProvider>);

describe("the two-step reminder", () => {
  it("counts the days left, to the nearest day", () => { expect(daysLeft(inDays(10), NOW)).toBe(10); expect(daysLeft(inDays(1), NOW)).toBe(1); expect(daysLeft(new Date(NOW - 5000).toISOString(), NOW)).toBe(0); });

  it("shows the banner and the first-entry dialog to a required role that has not enrolled", () => {
    mount(nudge());
    expect(screen.getByText(/Two-step verification is required in 10 days\./)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Set it up." })).toHaveAttribute("href", "/account?tab=security");
    expect(screen.getByRole("dialog", { name: "Protect your organisation with two-step verification" })).toHaveTextContent("about 2 minutes with an authenticator app");
    expect(screen.getByRole("link", { name: "Set up now" })).toHaveAttribute("href", "/account?tab=security");
  });

  it("renders nothing for anyone else: enrolled, not required, or no grace", () => {
    for (const n of [nudge({ enrolled: true }), nudge({ required: false }), nudge({ graceEndsAt: null })]) { const { container, unmount } = mount(n); expect(container).toBeEmptyDOMElement(); unmount(); }
  });

  it("Remind me later snoozes for a day on the server and closes the dialog, and the banner stays", async () => {
    let called = 0;
    server.use(http.post("/api/bff/v1/me/mfa-nudge", () => { called++; return HttpResponse.json({ snoozed_until: "x" }); }));
    mount(nudge());
    fireEvent.click(screen.getByRole("button", { name: "Remind me later" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(called).toBe(1); expect(screen.getByText(/required in 10 days/)).toBeInTheDocument();
  });

  it("stays quiet while a snooze is in force", () => {
    mount(nudge({ snoozedUntil: new Date(NOW + 3_600_000).toISOString() }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(); expect(screen.getByText(/required in 10 days/)).toBeInTheDocument();
  });

  it("a snooze that has run out brings the dialog back", () => {
    mount(nudge({ snoozedUntil: new Date(NOW - 3_600_000).toISOString() }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("no dialog on the account pages, where the person is setting it up", () => {
    nav.pathname = "/account";
    mount(nudge());
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(); expect(screen.getByText(/required in 10 days/)).toBeInTheDocument();
  });

  it("the banner can be closed for the session until the last three days, then it cannot", () => {
    const { unmount } = mount(nudge({ snoozedUntil: new Date(NOW + 3_600_000).toISOString() }));
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByText(/required in/)).not.toBeInTheDocument();
    unmount();
    mount(nudge({ graceEndsAt: inDays(3), snoozedUntil: new Date(NOW + 3_600_000).toISOString() }));
    expect(screen.getByText(/required in 3 days/)).toBeInTheDocument(); expect(screen.queryByRole("button", { name: "Close" })).not.toBeInTheDocument();
  });

  it("says one day and today in their own words", () => {
    const { unmount } = mount(nudge({ graceEndsAt: inDays(1), snoozedUntil: inDays(1) })); expect(screen.getByText(/required in 1 day\./)).toBeInTheDocument(); unmount();
    mount(nudge({ graceEndsAt: new Date(NOW + 60_000).toISOString(), snoozedUntil: inDays(1) }));
    expect(screen.getByText(/Two-step verification is required today\./)).toBeInTheDocument();
  });

  it("is translated", () => {
    mount(nudge({ snoozedUntil: inDays(1) }), "ar");
    expect(screen.getByRole("status")).toHaveTextContent("التحقق بخطوتين مطلوب خلال 10 أيام");
  });

  it("writes the proxy's hint: enrolled, the end of the grace, or nothing for a role that does not need it", async () => {
    expect(hintValue(nudge({ enrolled: true }))).toBe("enrolled");
    expect(hintValue(nudge({ graceEndsAt: "2026-11-10T00:00:00Z" }))).toBe(`grace:${Math.floor(new Date("2026-11-10T00:00:00Z").getTime() / 1000)}`);
    expect(hintValue(nudge({ graceEndsAt: null }))).toBe("expired");
    expect(hintValue(nudge({ required: false }))).toBe("");
    mount(nudge({ enrolled: true }));
    await waitFor(() => expect(document.cookie).toContain("sv_mfa=enrolled"));
  });
});
