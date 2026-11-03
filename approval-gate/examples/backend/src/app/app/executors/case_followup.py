"""send_case_followup: re-checks consent, suppression and quiet hours at send time. Aggregate cases can never be followed up."""
import uuid
from datetime import UTC, datetime, time

from app.core.distribution import next_allowed
from app.core.ports import Message
from app.db.repos import contacts as contacts_repo
from app.db.repos import cx, cx_cases, org_settings


async def execute(conn, notifier, approval: dict, base_url: str, now: datetime | None = None) -> dict:
    p = approval["payload"]
    case = await cx_cases.get(conn, uuid.UUID(p["case_id"]))
    now = now or datetime.now(UTC)
    if case is None or case.kind != "respondent" or not case.consented or case.contact_id is None:
        return {"sent": 0, "skipped": "no_consent"}
    ch = case.channel or "email"
    cons = await contacts_repo.consent_status(conn, case.contact_id, ch)
    ct = await contacts_repo.channels_of(conn, case.contact_id)
    addr = ct.email if ch == "email" else ct.phone_e164
    if cons != "opt_in" or not addr or await contacts_repo.is_suppressed(conn, ch, addr):
        return {"sent": 0, "skipped": "no_consent"}
    s = await org_settings.get(conn)
    q = (s.quiet_start, s.quiet_end, s.tz) if s else (time(21, 0), time(8, 0), "Asia/Dubai")
    when = next_allowed(now, q[2], q[0], q[1])
    if when > now:
        return {"sent": 0, "deferred": 1, "next_release": when.isoformat()}
    lang = ct.language if ct.language in ("en", "ar", "ur", "hi", "ru", "fil") else "en"
    key = f"case-{case.id}-{approval['id']}"
    rc = await notifier.send(Message(ch, addr, f"case-followup-{lang}", lang, {"subject": "Following up on your feedback", "text": p["message"]}, key))
    await cx.add_followup_event(conn, case.org_id, case.id, f"Follow-up sent via {ch}")
    await cx.mark_contacted(conn, case.id)
    return {"sent": 1, "provider_ref": rc.provider_ref}
