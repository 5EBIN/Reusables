// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Content from "../app/(generated)/auth/content";
import { Behaviors } from "../components/Behaviors";
import { I18nProvider } from "../components/I18n";
import { mfa, nav } from "./setup";
import { server, useMsw } from "./msw";

// Credentials go from the browser straight to Supabase Auth; the stand-in below records what the page sends and answers as the test says.
const sb = vi.hoisted(() => ({ signIn: vi.fn(), signUp: vi.fn(), resend: vi.fn(), getUser: vi.fn(), update: vi.fn(), resetEmail: vi.fn(), signOut: vi.fn() }));
vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({ auth: { signInWithPassword: sb.signIn, signUp: sb.signUp, resend: sb.resend, getUser: sb.getUser, updateUser: sb.update, resetPasswordForEmail: sb.resetEmail, signOut: sb.signOut } }),
}));

useMsw();
afterEach(cleanup);
beforeEach(() => {
  nav.replace.mockClear(); nav.search = new URLSearchParams();
  for (const f of Object.values(sb)) f.mockReset().mockResolvedValue({ data: {}, error: null });
  sb.getUser.mockResolvedValue({ data: { user: { id: "u1" } }, error: null });
  server.use(http.get("/api/org", () => HttpResponse.json([{ id: "o1", name: "A", role: "analyst" }])), http.post("/api/org", () => HttpResponse.json({ ok: true })));
});

const mount = (lang: "en" | "ar" = "en") => render(<I18nProvider initial={lang}><Content /><Behaviors /></I18nProvider>);
const panel = (n: string) => document.querySelector(`[data-panel=${n}]`) as HTMLElement;
const type = (el: Element, v: string) => fireEvent.change(el, { target: { value: v } });
const signInWith = (email: string, pw: string) => {
  const [e, p] = panel("signin").querySelectorAll("input.in");
  type(e, email); type(p, pw);
  fireEvent.click(panel("signin").querySelector("button.btn.pri")!);
};

describe("password reset link", () => {
  it("opens the new-password panel (the email link signed the user in), sets the password with Supabase, signs out and returns to sign-in", async () => {
    let revokedAll = false;
    server.use(http.post("/api/bff/v1/auth/revoke-all", () => { revokedAll = true; return new HttpResponse(null, { status: 204 }); }));
    nav.search = new URLSearchParams({ reset: "1" });
    mount();
    const pw = await screen.findByLabelText("New password");
    await waitFor(() => expect(panel("newpw")).toHaveClass("on"));
    type(pw, "a long enough passphrase 1"); fireEvent.click(panel("newpw").querySelector("button.btn.pri")!);
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/auth?done=reset"));
    expect(sb.update).toHaveBeenCalledWith({ password: "a long enough passphrase 1" }); expect(sb.signOut).toHaveBeenCalledWith({ scope: "global" });
    expect(revokedAll).toBe(true);                                  // the API stops accepting every older token of this account as well
  });
  it("a reset link that did not sign anyone in goes back to Sign in with a clear message", async () => {
    sb.getUser.mockResolvedValue({ data: { user: null }, error: null });
    nav.search = new URLSearchParams({ reset: "1" });
    mount();
    await waitFor(() => expect(panel("signin")).toHaveClass("on"));
    expect(await screen.findByRole("alert")).toHaveTextContent("invalid or has expired");
  });
  it.each([["weak_password", "not allowed"], ["session_not_found", "invalid or has expired"]] as const)("explains a refused reset [%s]", async (code, text) => {
    sb.update.mockResolvedValue({ data: {}, error: { code, status: 422 } });
    nav.search = new URLSearchParams({ reset: "1" });
    mount();
    type(await screen.findByLabelText("New password"), "a long enough passphrase 1");
    fireEvent.click(panel("newpw").querySelector("button.btn.pri")!);
    expect(await screen.findByRole("alert")).toHaveTextContent(text);
    expect(nav.replace).not.toHaveBeenCalled();
  });
  it("without the reset flag the new-password panel is never shown", () => {
    mount(); expect(panel("newpw")).not.toHaveClass("on");
  });
  it("Forgot password opens the reset panel; sending says where the link went (same answer for any address); Back to sign in returns", async () => {
    mount();
    expect(panel("reset")).not.toHaveClass("on");
    fireEvent.click(screen.getByText("Forgot password?"));
    await waitFor(() => expect(panel("reset")).toHaveClass("on"));
    sb.resetEmail.mockResolvedValue({ data: null, error: { status: 400 } });
    type(panel("reset").querySelector("input.in")!, "user@example.com");
    fireEvent.click(panel("reset").querySelector("button.btn.pri")!);
    expect(await screen.findByRole("status")).toHaveTextContent("If an account exists for user@example.com, we've sent a password reset link. It may take a few minutes.");
    const [email, o] = sb.resetEmail.mock.calls[0];
    expect(email).toBe("user@example.com"); expect(o.redirectTo).toBe(`${location.origin}/auth/confirm?next=${encodeURIComponent("/auth?reset=1")}`);
    fireEvent.click(screen.getByText("Back to sign in"));
    await waitFor(() => expect(panel("signin")).toHaveClass("on"));
  });
});

describe("invitation link", () => {
  it("accepts the token after sign-in, switches to the inviting org and lands (even with no org yet)", async () => {
    let tok: any, sw: any;
    server.use(http.get("/api/org", () => HttpResponse.json([])),
      http.post("/api/bff/v1/invitations/accept", async ({ request }) => { tok = await request.json(); return HttpResponse.json({ org_id: "o9", role: "analyst" }); }),
      http.post("/api/org", async ({ request }) => { sw = await request.json(); return HttpResponse.json({ ok: true }); }));
    nav.search = new URLSearchParams({ invite: "tok-abcdefghijklmnop" });
    mount(); signInWith("user@example.com", "x".repeat(12));
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/overview"));
    expect(tok).toEqual({ token: "tok-abcdefghijklmnop" }); expect(sw).toEqual({ id: "o9" });
  });
  it.each([["en", "invalid or has expired"], ["ar", "غير صالحة"]] as const)("shows a clear error and stays put when the invitation is rejected [%s]", async (lang, text) => {
    server.use(http.get("/api/org", () => HttpResponse.json([])), http.post("/api/bff/v1/invitations/accept", () => HttpResponse.json({ detail: "x" }, { status: 404 })));
    nav.search = new URLSearchParams({ invite: "tok-abcdefghijklmnop" });
    mount(lang); signInWith("user@example.com", "x".repeat(12));
    await waitFor(() => expect(document.body).toHaveTextContent(text));
    expect(nav.replace).not.toHaveBeenCalled();
  });
});

describe("sign in", () => {
  it("masks the password field, signs in with Supabase from the browser, picks the first organisation and lands on the overview", async () => {
    let picked: any;
    server.use(http.post("/api/org", async ({ request }) => { picked = await request.json(); return HttpResponse.json({ ok: true }); }));
    mount();
    expect(panel("signin").querySelectorAll("input.in")[1]).toHaveAttribute("type", "password");
    signInWith("user@example.com", "correct horse battery");
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/overview"));
    expect(sb.signIn).toHaveBeenCalledWith({ email: "user@example.com", password: "correct horse battery", options: { captchaToken: undefined } });
    expect(picked).toEqual({ id: "o1" });
  });

  it("drops a stale two-step hint left by whoever used the browser before, so the proxy cannot bounce the new session back to sign-in", async () => {
    document.cookie = "sv_mfa=enrolled; path=/";
    server.use(http.post("/api/org", () => HttpResponse.json({ ok: true })));
    mount();
    signInWith("user@example.com", "correct horse battery");
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/overview"));
    expect(document.cookie).not.toContain("sv_mfa=enrolled");
  });

  it("shows a spinner on the button from the press until the next page is on its way", async () => {
    server.use(http.post("/api/org", () => HttpResponse.json({ ok: true })));
    mount();
    signInWith("user@example.com", "correct horse battery");
    const btn = panel("signin").querySelector("button.btn.pri") as HTMLButtonElement;
    await waitFor(() => expect(btn).toHaveClass("busy")); expect(btn).toBeDisabled();
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/overview"));
    expect(btn).toHaveClass("busy");                                   // still busy while the dashboard loads
  });

  it("honours a safe ?next= and ignores open redirects", async () => {
    for (const [next, want] of [["/surveys", "/surveys"], ["//evil.example", "/overview"], ["https://evil.example", "/overview"]] as const) {
      nav.search = new URLSearchParams({ next }); nav.replace.mockClear();
      const { unmount } = mount();
      signInWith("user@example.com", "x".repeat(12));
      await waitFor(() => expect(nav.replace).toHaveBeenCalledWith(want));
      unmount();
    }
  });

  it("shows one generic message for bad credentials and the wait time when Supabase rate-limits", async () => {
    sb.signIn.mockResolvedValue({ data: {}, error: { status: 400, code: "invalid_credentials" } });
    mount();
    signInWith("user@example.com", "wrong-password-1");
    expect(await screen.findByRole("alert")).toHaveTextContent("Email or password is incorrect.");
    sb.signIn.mockResolvedValue({ data: {}, error: { status: 429, code: "over_request_rate_limit" } });
    fireEvent.click(panel("signin").querySelector("button.btn.pri")!);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("60"));
    expect(nav.replace).not.toHaveBeenCalled();
  });

  it("a user with no organisation is asked to name one", async () => {
    server.use(http.get("/api/org", () => HttpResponse.json([])));
    mount(); signInWith("user@example.com", "x".repeat(12));
    expect(await screen.findByLabelText("Organisation name")).toBeInTheDocument();
    await waitFor(() => expect(panel("org")).toHaveClass("on"));
    expect(nav.replace).not.toHaveBeenCalled();
  });

  it("an unconfirmed address is told to open the link it was sent", async () => {
    sb.signIn.mockResolvedValue({ data: {}, error: { status: 400, code: "email_not_confirmed" } });
    mount(); signInWith("user@example.com", "x".repeat(12));
    expect(await screen.findByRole("alert")).toHaveTextContent("Confirm your email first");
  });

  it("goes to the two-step panel when the account has it enabled, and verifies the code with Supabase", async () => {
    mfa.state.mockResolvedValue({ enrolled: true, factorId: "f1", aal2: false, needsVerify: true });
    mfa.verifyCode.mockImplementation(async (_id: string, code: string) => code === "482913");
    mount(); signInWith("user@example.com", "x".repeat(12));
    await waitFor(() => expect(panel("mfa")).toHaveClass("on"));
    const boxes = panel("mfa").querySelectorAll("input.in");
    "482911".split("").forEach((d, i) => type(boxes[i], d));
    fireEvent.click(panel("mfa").querySelector("button.btn.pri")!);
    expect(await screen.findByRole("alert")).toHaveTextContent("not valid");
    type(boxes[5], "3");
    fireEvent.click(panel("mfa").querySelector("button.btn.pri")!);
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/overview"));
    expect(mfa.verifyCode).toHaveBeenLastCalledWith("f1", "482913");
  });

  it("an administrator with no authenticator whose grace is over (the API says mfa_required) is walked through setting one up before landing", async () => {
    server.use(http.get("/api/org", () => HttpResponse.json([{ id: "o1", name: "A", role: "client_admin" }])), http.get("/api/bff/v1/me", () => HttpResponse.json({ mfa_required: true })));
    mount(); signInWith("user@example.com", "x".repeat(12));
    await waitFor(() => expect(panel("mfa")).toHaveClass("on"));
    expect(await screen.findByAltText(/QR code/)).toBeInTheDocument(); expect(screen.getByText("JBSWY3DPEHPK3PXP")).toBeInTheDocument();
    expect(nav.replace).not.toHaveBeenCalled();
    const boxes = panel("mfa").querySelectorAll("input.in");
    "123456".split("").forEach((d, i) => type(boxes[i], d));
    fireEvent.click(panel("mfa").querySelector("button.btn.pri")!);
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/overview"));
    expect(mfa.verifyCode).toHaveBeenCalledWith("f-new", "123456");
  });

  it("an administrator with no authenticator who is still inside the grace lands on the dashboard, with no set-up forced", async () => {
    server.use(http.get("/api/org", () => HttpResponse.json([{ id: "o1", name: "A", role: "client_admin" }])), http.get("/api/bff/v1/me", () => HttpResponse.json({ mfa_required: false, grace_ends_at: "2099-01-01T00:00:00Z" })));
    mount(); signInWith("user@example.com", "x".repeat(12));
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/overview"));
    expect(mfa.startEnrol).not.toHaveBeenCalled();
  });

  it("an enrolled administrator is challenged for the code, grace or not", async () => {
    server.use(http.get("/api/org", () => HttpResponse.json([{ id: "o1", name: "A", role: "client_admin" }])), http.get("/api/bff/v1/me", () => HttpResponse.json({ mfa_required: true, enrolled: true })));
    mfa.state.mockResolvedValue({ enrolled: true, factorId: "f1", aal2: false, needsVerify: true });
    mount(); signInWith("user@example.com", "x".repeat(12));
    await waitFor(() => expect(panel("mfa")).toHaveClass("on"));
    expect(mfa.startEnrol).not.toHaveBeenCalled(); expect(nav.replace).not.toHaveBeenCalled();
  });

  it("an administrator whose authenticator set-up cannot start stays on the two-step panel with a Retry and never reaches the dashboard", async () => {
    server.use(http.get("/api/org", () => HttpResponse.json([{ id: "o1", name: "A", role: "client_admin" }])), http.get("/api/bff/v1/me", () => HttpResponse.json({ mfa_required: true })));
    mfa.startEnrol.mockResolvedValueOnce(null);
    mount(); signInWith("user@example.com", "x".repeat(12));
    expect(await screen.findByRole("alert")).toHaveTextContent("Two-step setup is unavailable right now");
    expect(panel("mfa")).toHaveClass("on"); expect(nav.replace).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Retry"));                     // the second attempt works: the QR shows and the box is usable
    expect(await screen.findByAltText(/QR code/)).toBeInTheDocument();
    expect(nav.replace).not.toHaveBeenCalled();
  });

  it("an analyst with no authenticator lands straight away (the second step is not required for the role)", async () => {
    server.use(http.get("/api/org", () => HttpResponse.json([{ id: "o1", name: "A", role: "analyst" }])));
    mount(); signInWith("user@example.com", "x".repeat(12));
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/overview"));
    expect(mfa.startEnrol).not.toHaveBeenCalled();
  });

  it("sent back by the API with mfa=1 it asks for the code again", async () => {
    mfa.state.mockResolvedValue({ enrolled: true, factorId: "f1", aal2: false, needsVerify: true });
    nav.search = new URLSearchParams({ mfa: "1", next: "/team" });
    mount();
    await waitFor(() => expect(panel("mfa")).toHaveClass("on"));
    const boxes = panel("mfa").querySelectorAll("input.in");
    "123456".split("").forEach((d, i) => type(boxes[i], d));
    fireEvent.click(panel("mfa").querySelector("button.btn.pri")!);
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/team"));
  });

  it("mfa=1 without a signed-in session is just the sign-in page", async () => {
    server.use(http.get("/api/org", () => HttpResponse.json({ detail: "x" }, { status: 401 })));
    nav.search = new URLSearchParams({ mfa: "1" });
    mount();
    await waitFor(() => expect(panel("signin")).toHaveClass("on"));
    expect(panel("mfa")).not.toHaveClass("on"); expect(mfa.state).not.toHaveBeenCalled();
  });

  it("one-time code boxes accept a pasted code", () => {
    mount();
    const boxes = panel("mfa").querySelectorAll<HTMLInputElement>("input.in");
    fireEvent.paste(boxes[0], { clipboardData: { getData: () => "48 29-13" } });
    expect([...panel("mfa").querySelectorAll<HTMLInputElement>("input.in")].map((b) => b.value).join("")).toBe("482913");
  });
});

describe("hidden steps", () => {
  it("the tab bar has only Sign in and Create account", () => {
    mount();
    expect([...document.querySelectorAll("[data-tabs=auth] [data-tab]")].map((b) => b.textContent)).toEqual(["Sign in", "Create account"]);
  });
  it.each(["mfa", "verify", "reset", "org", "newpw"])("the %s panel cannot be opened by a URL flag or by clicking", async (name) => {
    nav.search = new URLSearchParams({ tab: name, panel: name, step: name });
    mount(); await Promise.resolve();
    expect(panel(name)).not.toHaveClass("on");
    expect(document.querySelector(`[data-tab=${name}]`)).toBeNull();                       // no button to click
    document.querySelectorAll("[data-tab]").forEach((b) => fireEvent.click(b));            // clicking every tab there is opens only Sign in or Create account
    expect(panel(name)).not.toHaveClass("on");
  });
});

describe("register and verify", () => {
  const fill = () => {
    const p = panel("register"); const inputs = p.querySelectorAll("input.in");
    type(inputs[0], "Jordan"); type(inputs[1], "Lee"); type(inputs[2], "user@example.com"); type(inputs[3], "a much better passphrase");
    fireEvent.click(p.querySelector("input[type=checkbox]")!);
    fireEvent.click(p.querySelector("button.btn.pri")!);
  };
  it("requires the terms, rejects weak passwords with Supabase's reason, then shows where the confirmation link was sent", async () => {
    sb.signUp.mockImplementation(async ({ password }: { password: string }) => (password === "password123" ? { data: {}, error: { code: "weak_password", status: 422 } } : { data: {}, error: null }));
    mount();
    const p = panel("register");
    const inputs = p.querySelectorAll("input.in");
    type(inputs[0], "Jordan"); type(inputs[1], "Lee"); type(inputs[2], "user@example.com"); type(inputs[3], "password123");
    fireEvent.click(p.querySelector("button.btn.pri")!);
    expect(await screen.findByRole("alert")).toHaveTextContent("Terms");
    expect(sb.signUp).not.toHaveBeenCalled();
    fireEvent.click(p.querySelector("input[type=checkbox]")!);
    fireEvent.click(p.querySelector("button.btn.pri")!);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("not allowed"));
    expect(panel("verify")).not.toHaveClass("on");
    type(inputs[3], "a much better passphrase");
    fireEvent.click(p.querySelector("button.btn.pri")!);
    await waitFor(() => expect(panel("verify")).toHaveClass("on"));
    const o = sb.signUp.mock.calls.at(-1)![0];
    expect(o.email).toBe("user@example.com"); expect(o.options.emailRedirectTo).toBe(`${location.origin}/auth/confirm?next=${encodeURIComponent("/auth?welcome=1")}`); expect(o.options.data).toEqual({ first_name: "Jordan", last_name: "Lee" });
    expect(panel("verify")).toHaveTextContent("We sent a confirmation link to user@example.com. Open it to activate your account, then come back and sign in.");
  });
  it("the verify panel shows a 60 s resend countdown; Wrong email? goes back to Create account", async () => {
    mount(); fill();
    await waitFor(() => expect(panel("verify")).toHaveClass("on"));
    expect(screen.getByText("Resend link")).toBeDisabled(); expect(panel("verify")).toHaveTextContent("1:00");
    expect(sb.resend).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Wrong email? Change it"));
    await waitFor(() => expect(panel("register")).toHaveClass("on"));
  });
  it("Resend link sends the sign-up email again once the countdown is over, then counts down again", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      mount(); fill();
      await waitFor(() => expect(panel("verify")).toHaveClass("on"));
      for (let i = 0; i < 61; i++) await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
      await waitFor(() => expect(screen.getByText("Resend link")).toBeEnabled());
      fireEvent.click(screen.getByText("Resend link"));
      await waitFor(() => expect(sb.resend).toHaveBeenCalledWith(expect.objectContaining({ type: "signup", email: "user@example.com" })));
      await waitFor(() => expect(screen.getByText("Resend link")).toBeDisabled());
    } finally { vi.useRealTimers(); }
  });
  it("after the link signed the user in (?welcome=1) a user with no organisation is asked to name one, then lands on the dashboard (the grace starts; no forced set-up)", async () => {
    server.use(http.get("/api/org", () => HttpResponse.json([])),
      http.post("/api/org", async ({ request }) => HttpResponse.json({ id: "o1", name: ((await request.json()) as any).name }, { status: 201 })));
    nav.search = new URLSearchParams({ welcome: "1" });
    mount();
    const name = await screen.findByLabelText("Organisation name");
    await waitFor(() => expect(panel("org")).toHaveClass("on"));
    type(name, "<company> Properties");
    fireEvent.click(screen.getByText("Create organisation"));
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/overview"));            // the creator is an administrator with a grace: the dashboard, and the reminder banner there
    expect(mfa.startEnrol).not.toHaveBeenCalled();
  });
  it("?welcome=1 without a session is just the sign-in page", async () => {
    server.use(http.get("/api/org", () => HttpResponse.json({ detail: "x" }, { status: 401 })));
    nav.search = new URLSearchParams({ welcome: "1" });
    mount();
    await waitFor(() => expect(panel("signin")).toHaveClass("on"));
  });
  it("a failed or expired link (?error=confirm) says so on the sign-in page", async () => {
    nav.search = new URLSearchParams({ error: "confirm" });
    mount();
    expect(await screen.findByRole("alert")).toHaveTextContent("invalid or has expired");
    expect(panel("signin")).toHaveClass("on");
  });

  it("messages follow the interface language (Arabic)", async () => {
    sb.signIn.mockResolvedValue({ data: {}, error: { status: 400, code: "invalid_credentials" } });
    mount("ar"); signInWith("user@example.com", "x".repeat(12));
    expect(await screen.findByRole("alert")).toHaveTextContent("غير صحيحة");
  });
});
