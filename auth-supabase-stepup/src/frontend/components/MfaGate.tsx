"use client";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Modal } from "@/components/e/Modal";
import { bff, post } from "@/lib/client-api";
import { useMsg } from "@/lib/messages";

export type Nudge = {
  /** The person's role needs two-step verification. */
  required: boolean;
  enrolled: boolean;
  /** When the grace ends (ISO); set only while a required role who has not enrolled is inside it. */
  graceEndsAt: string | null;
  /** "Remind me later" is in force until this time (ISO). */
  snoozedUntil: string | null;
};

const DAY = 86_400_000;
/** Whole days to the end of the grace, to the nearest day (a grace that has just started says its full length even when the two clocks differ by a second). */
export const daysLeft = (endsAt: string, now = Date.now()) => Math.max(0, Math.round((new Date(endsAt).getTime() - now) / DAY));
/** In the last three days the banner stays: it cannot be closed. */
export const LOCKED_DAYS = 3;
const DISMISSED = "sv_mfa_banner_closed";

/** A hint for the proxy only (it decides where to send a request before any backend call): enrolled, or when the grace ends. The API never reads it. */
export const hintValue = (n: Nudge): string => (!n.required ? "" : n.enrolled ? "enrolled" : n.graceEndsAt ? `grace:${Math.floor(new Date(n.graceEndsAt).getTime() / 1000)}` : "expired");

/** The reminder shown to a person who must set up two-step verification and has not yet: a banner on every page and, until it is snoozed, a dialog. Renders nothing for anyone else. */
export function MfaGate({ nudge }: { nudge: Nudge }) {
  const t = useMsg(); const path = usePathname() ?? "";
  const [closed, setClosed] = useState(false); const [snoozed, setSnoozed] = useState(false); const [busy, setBusy] = useState(false);
  useEffect(() => {
    try { document.cookie = `sv_mfa=${hintValue(nudge)}; path=/; max-age=${60 * 60 * 24 * 30}; samesite=lax`; } catch { /* a hint only */ }
    try { setClosed(sessionStorage.getItem(DISMISSED) === "1"); } catch { /* private window */ }
  }, [nudge.required, nudge.enrolled, nudge.graceEndsAt]);                    // eslint-disable-line react-hooks/exhaustive-deps
  if (!nudge.required || nudge.enrolled || !nudge.graceEndsAt) return null;
  const n = daysLeft(nudge.graceEndsAt);
  const locked = n <= LOCKED_DAYS;
  const onAccount = path.startsWith("/account");
  const quiet = snoozed || (nudge.snoozedUntil !== null && new Date(nudge.snoozedUntil).getTime() > Date.now());
  const later = async () => { setBusy(true); await post(bff("v1/me/mfa-nudge")); setBusy(false); setSnoozed(true); };
  const close = () => { setClosed(true); try { sessionStorage.setItem(DISMISSED, "1"); } catch { /* not remembered */ } };
  return (
    <>
      {(locked || !closed) && (
        <div className="notice warn" role="status" style={{ margin: "0 24px 0", justifyContent: "space-between", alignItems: "center" }} data-mfa-banner>
          <span>{n <= 0 ? t("mfa_banner_today") : n === 1 ? t("mfa_banner_one") : t("mfa_banner", { n })} <a href="/account?tab=security" style={{ fontWeight: 600 }}>{t("mfa_banner_link")}</a></span>
          {!locked && <button className="btn sm ghost" onClick={close} aria-label={t("mfa_banner_close")}>×</button>}
        </div>
      )}
      {!quiet && !onAccount && (
        <Modal title={t("mfa_modal_title")} onClose={() => void later()}
          footer={<><button className="btn" disabled={busy} onClick={() => void later()}>{t("mfa_remind_later")}</button><a className="btn pri" href="/account?tab=security">{t("mfa_set_up_now")}</a></>}>
          <p className="sm">{t("mfa_modal_body")}</p>
        </Modal>
      )}
    </>
  );
}
