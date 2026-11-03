"""launch_360_cycle: issue single-use hashed tokens to approved raters, send invitations, schedule the reminder cadence."""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, UTC
from zoneinfo import ZoneInfo

from app.adapters.queue_pg import PgQueue
from app.core.ports import Message
from app.db.repos import employees, feedback360


def _h(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


async def execute(conn, notifier, approval: dict, base_url: str, now=None) -> dict:
    cid = uuid.UUID(approval["payload"]["cycle_id"])
    cyc = (await feedback360.cycle(conn, cid)).model_dump()
    now = now or datetime.now(UTC)
    raters = [r.model_dump() for r in await feedback360.raters_to_invite(conn, cid)]
    expires = cyc["deadline"] or now + timedelta(days=30)
    sent = failed = 0
    for r in raters:
        tok = secrets.token_urlsafe(32)
        email = r["email"]
        if not email and r["employee_id"]:
            email = await employees.email_of(conn, r["employee_id"])
        await feedback360.invite_rater(conn, r["id"], _h(tok), expires)
        if not email:
            failed += 1
            continue
        try:
            await notifier.send(Message("email", email, "360-invite", "en", {"subject": "360 feedback request", "text": f"{base_url}/360/{tok}"}, f"360-{r['id']}"))
            sent += 1
        except Exception:
            failed += 1
    await feedback360.go_live(conn, cid)
    q = PgQueue()
    z = ZoneInfo("Asia/Dubai")
    for d in cyc["reminder_days"]:
        when = (cyc["deadline"] - timedelta(days=d)) if cyc["deadline"] else None
        if when and when > now:
            when = when.astimezone(z).replace(hour=9, minute=0, second=0, microsecond=0).astimezone(UTC)
            await q.enqueue(conn, "reminders_360", {"cycle_id": str(cid), "day_offset": d}, run_after=when)
    return {"cycle_id": str(cid), "invited": sent, "failed": failed, "reminders_scheduled": len(cyc["reminder_days"])}


async def remind(conn, notifier, cycle_id: uuid.UUID, day_offset: int, base_url: str, now=None) -> dict:
    """Reminders go ONLY to raters who have not completed (completion tracked on the rater). Tokens rotate so links stay single-use."""
    cyc = await feedback360.cycle(conn, cycle_id)
    cyc = cyc.model_dump() if cyc else None
    if not cyc or cyc["status"] != "live":
        return {"sent": 0, "escalated": 0}
    todo = [r.model_dump() for r in await feedback360.invited_raters(conn, cycle_id)]
    sent = esc = 0
    per_subject: dict = {}
    for r in todo:
        if await feedback360.reminder_sent(conn, r["id"], day_offset):
            continue                                                              # replay-safe
        email = r["email"] or (await employees.email_of(conn, r["employee_id"]) if r["employee_id"] else None)
        if not email:
            continue
        tok = secrets.token_urlsafe(32)
        await feedback360.rotate_rater_token(conn, r["id"], _h(tok))
        await notifier.send(Message("email", email, "360-reminder", "en", {"subject": "Reminder: 360 feedback", "text": f"{base_url}/360/{tok}"}, f"360r-{r['id']}-{day_offset}"))
        await feedback360.log_reminder(conn, r["org_id"], r["id"], day_offset)
        sent += 1
        per_subject[r["subject_id"]] = per_subject.get(r["subject_id"], 0) + 1
    for sid, outstanding in per_subject.items():
        misses = await feedback360.max_reminders_for_subject(conn, sid)
        if misses and misses >= cyc["escalate_after"]:
            mgr = await feedback360.subject_manager_email(conn, sid)
            if mgr:
                await notifier.send(Message("email", mgr, "360-escalation", "en", {"subject": "360 feedback outstanding", "text": f"{outstanding} outstanding responses for one of your reports."}, f"360e-{sid}-{day_offset}"))
                esc += 1
    return {"sent": sent, "escalated": esc}
