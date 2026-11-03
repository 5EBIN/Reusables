"""start_conversations: consent/suppression/quiet-hours re-checked at send time; one conversation per (survey, contact, channel); replay-safe."""
import json
import uuid
from datetime import UTC, datetime, time

from app.app.audience import load_audience
from app.core.conversation import addr_hash, plan_turns, render
from app.core.distribution import next_allowed
from app.core.ports import Message
from app.db.repos import conversations, org_settings, surveys


async def execute(conn, notifier, approval: dict, base_url: str, now: datetime | None = None) -> dict:
    p = approval["payload"]
    sid, ch = uuid.UUID(p["survey_id"]), p["channel"]
    now = now or datetime.now(UTC)
    d = await surveys.latest_published_definition(conn, sid)
    defn = json.loads(d)
    s = await org_settings.get(conn)
    quiet = (s.quiet_start, s.quiet_end, s.tz) if s else (time(21, 0), time(8, 0), "Asia/Dubai")
    contacts, (aud, plan) = await load_audience(conn, [uuid.UUID(x) for x in p["list_ids"]], [ch])
    by = {c["id"]: c for c in contacts}
    rec = {"started": 0, "deferred": 0, "skipped": 0, "audience": aud.will_receive}
    when = next_allowed(now, quiet[2], quiet[0], quiet[1]) if quiet[0] is not None else now
    for cid, chan, reason in plan:
        cvid = uuid.uuid5(approval["id"], f"{cid}:{chan}")
        if await conversations.exists(conn, cvid):
            rec["started"] += 1; continue                                  # replay-safe
        if reason != "ok":
            rec["skipped"] += 1; continue
        if when > now:
            rec["deferred"] += 1; continue
        c = by[cid]
        lang = c["language"] if c["language"] in ("en", "ar") else "en"
        turns = plan_turns(defn, lang)
        addr = c["phone"]
        if not addr:
            rec["skipped"] += 1; continue
        await conversations.insert(conn, approval["org_id"], cvid, sid, cid, chan, addr_hash(chan, addr), lang, approval["id"])
        await notifier.send(Message(chan, addr, f"chat-{lang}", lang, {"text": render(turns[0], lang) + "\n" + ("أرسل إيقاف لإلغاء الاشتراك." if lang == "ar" else "Reply STOP to opt out.")}, f"conv-{cvid}-0"))
        rec["started"] += 1
    if rec["deferred"]:
        rec["next_release"] = when.isoformat()
    return rec
