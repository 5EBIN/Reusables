"""send_survey_invites / send_reminder: re-checks consent, suppression, quiet hours, quota AT SEND TIME; one delivery per (contact, channel)."""
import hashlib
import json
import secrets
import uuid
from datetime import datetime, time, UTC

from app.app.audience import load_audience
from app.core.distribution import next_allowed, render_template
from app.core.ports import Message
from app.db.repos import deliveries, invitations, org_settings


def _hash(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


async def execute(conn, notifier, approval: dict, base_url: str, now: datetime | None = None) -> dict:
    p = approval["payload"]
    inv = (await invitations.get(conn, uuid.UUID(p["invitation_id"]))).model_dump()
    now = now or datetime.now(UTC)
    settings = await org_settings.get(conn)
    quiet = (settings.quiet_start, settings.quiet_end, settings.tz) if settings else (time(21, 0), time(8, 0), "Asia/Dubai")
    quota = settings.daily_quota if settings else 5000
    sent_today = await deliveries.sent_today(conn)
    contacts, (aud, plan) = await load_audience(conn, inv["list_ids"], inv["channels"])
    by_id = {c["id"]: c for c in contacts}
    done = set()
    if inv["kind"] == "reminder":
        done = await deliveries.completed_contacts(conn, inv["id"])
    receipt = {"sent": 0, "deferred": 0, "skipped": 0, "failed": 0, "audience": aud.will_receive, "exclusions": {
        "no_consent": aud.no_consent, "suppressed": aud.suppressed, "recently_contacted": aud.recently_contacted}}
    for cid, ch, reason in plan:
        did = uuid.uuid5(inv["id"], f"{cid}:{ch}")
        exists = await deliveries.status_of(conn, did)
        if exists in ("sent", "delivered", "skipped"):
            receipt["sent" if exists != "skipped" else "skipped"] += 1
            continue                                                  # replay-safe
        if reason != "ok" or cid in done:
            await deliveries.insert_skipped(conn, inv["org_id"], did, inv["id"], cid, ch, reason if reason != "ok" else "completed")
            receipt["skipped"] += 1
            continue
        when = now
        if quiet[0] is not None:
            when = next_allowed(now, quiet[2], quiet[0], quiet[1])
        if when > now:
            await deliveries.upsert_deferred(conn, inv["org_id"], did, inv["id"], cid, ch, when)
            receipt["deferred"] += 1
            continue
        if ch != "email" and sent_today + receipt["sent"] >= quota:
            await deliveries.insert_skipped(conn, inv["org_id"], did, inv["id"], cid, ch, "quota")
            receipt["skipped"] += 1
            continue
        c = by_id[cid]
        token = secrets.token_urlsafe(32)
        lang = c["language"] if c["language"] in ("en", "ar", "ur", "hi", "ru", "fil") else "en"
        body = json.loads(inv["body"]).get(lang) or json.loads(inv["body"]).get("en", "")
        first = (c["name"] or "").split(" ")[0]
        text = render_template(body, {"first_name": first, "name": c["name"] or "", "link": f"{base_url}/i/{token}"})
        try:
            rc = await notifier.send(Message(ch, c["email"] if ch == "email" else c["phone"], f"invite-{lang}", lang, {"text": text}, str(did)))
            await deliveries.upsert_sent(conn, inv["org_id"], did, inv["id"], cid, ch, rc.provider_ref, _hash(token))
            receipt["sent"] += 1
        except Exception as e:  # provider failure is recorded, never raised past the executor
            await deliveries.upsert_failed(conn, inv["org_id"], did, inv["id"], cid, ch, str(e)[:300])
            receipt["failed"] += 1
    counts = await deliveries.status_counts(conn, inv["id"])
    receipt.update(sent=counts.get("sent", 0) + counts.get("delivered", 0), deferred=counts.get("deferred", 0), skipped=counts.get("skipped", 0), failed=counts.get("failed", 0))
    nxt = await deliveries.next_deferred_release(conn, inv["id"])
    receipt["next_release"] = nxt.isoformat() if nxt else None
    await invitations.set_status(conn, inv["id"], "sending" if nxt else "sent")
    return receipt
