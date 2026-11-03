import { beforeEach, describe, expect, it, vi } from "vitest";

// The real helpers (tests/setup.ts stands them in for page tests) against a stand-in browser client.
vi.unmock("@/lib/supabase/mfa");
const m = vi.hoisted(() => ({ aal: vi.fn(), list: vi.fn(), enroll: vi.fn(), unenroll: vi.fn(), cv: vi.fn() }));
vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({ auth: { mfa: { getAuthenticatorAssuranceLevel: m.aal, listFactors: m.list, enroll: m.enroll, unenroll: m.unenroll, challengeAndVerify: m.cv } } }),
}));
import { mfaState, removeFactor, startEnrol, verifyCode } from "../lib/supabase/mfa";

beforeEach(() => {
  m.aal.mockReset().mockResolvedValue({ data: { currentLevel: "aal1", nextLevel: "aal1" } });
  m.list.mockReset().mockResolvedValue({ data: { totp: [], all: [] } });
  m.enroll.mockReset().mockResolvedValue({ data: { id: "f2", totp: { qr_code: "data:image/svg+xml;utf8,<svg/>", secret: "KEY" } }, error: null });
  m.unenroll.mockReset().mockResolvedValue({ error: null });
  m.cv.mockReset().mockResolvedValue({ data: {}, error: null });
});

describe("two-step state", () => {
  it("not enrolled", async () => {
    expect(await mfaState()).toEqual({ enrolled: false, factorId: null, aal2: false, needsVerify: false });
  });
  it("enrolled but this session has not passed the second step", async () => {
    m.list.mockResolvedValue({ data: { totp: [{ id: "f1" }], all: [{ id: "f1" }] } });
    m.aal.mockResolvedValue({ data: { currentLevel: "aal1", nextLevel: "aal2" } });
    expect(await mfaState()).toEqual({ enrolled: true, factorId: "f1", aal2: false, needsVerify: true });
  });
  it("enrolled and verified in this session", async () => {
    m.list.mockResolvedValue({ data: { totp: [{ id: "f1" }], all: [{ id: "f1" }] } });
    m.aal.mockResolvedValue({ data: { currentLevel: "aal2", nextLevel: "aal2" } });
    expect(await mfaState()).toMatchObject({ enrolled: true, aal2: true, needsVerify: false });
  });
});

describe("enrolment and codes", () => {
  it("removes half-finished enrolments first, then enrols a TOTP factor", async () => {
    m.list.mockResolvedValue({ data: { totp: [], all: [{ id: "old", factor_type: "totp", status: "unverified" }, { id: "keep", factor_type: "totp", status: "verified" }] } });
    expect(await startEnrol()).toEqual({ factorId: "f2", qr: "data:image/svg+xml;utf8,<svg/>", secret: "KEY" });
    expect(m.unenroll).toHaveBeenCalledTimes(1); expect(m.unenroll).toHaveBeenCalledWith({ factorId: "old" });
    expect(m.enroll.mock.calls[0][0]).toMatchObject({ factorType: "totp" });
  });
  it("reports a failed enrolment as null", async () => {
    m.enroll.mockResolvedValue({ data: null, error: { message: "x" } });
    expect(await startEnrol()).toBeNull();
  });
  it("verifyCode is true only when Supabase accepts the code", async () => {
    expect(await verifyCode("f1", "123456")).toBe(true); expect(m.cv).toHaveBeenCalledWith({ factorId: "f1", code: "123456" });
    m.cv.mockResolvedValue({ data: null, error: { message: "bad" } });
    expect(await verifyCode("f1", "000000")).toBe(false);
  });
  it("removeFactor reports success and failure", async () => {
    expect(await removeFactor("f1")).toBe(true);
    m.unenroll.mockResolvedValue({ error: { message: "aal2 required" } });
    expect(await removeFactor("f1")).toBe(false);
  });
});
