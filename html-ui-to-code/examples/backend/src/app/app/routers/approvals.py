import json
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.adapters.queue_pg import PgQueue
from app.app.deps import OrgCtx, org_ctx
from app.app.audience import audience_preview
from app.app.routers.surveys import WRITERS
from app.core.approvals import RISK, ApprovalError, action_subtitle, action_title, confirmation, decide
from app.db.repos import approvals as repo
from app.db.repos import cx_cases as cases_repo
from app.db.repos import feedback_cycles as cycles_repo
from app.db.repos import invitations as invitations_repo
from app.db.repos import surveys as surveys_repo
from app.db.repos import users as users_repo

router = APIRouter(prefix="/v1/approvals", tags=["approvals"])
Q = PgQueue()


class Propose(BaseModel):
    action_type: Literal["send_survey_invites", "send_reminder", "publish_survey_version", "launch_360_cycle", "send_case_followup", "start_conversations"]
    payload: dict = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=8, max_length=100)
    scheduled_for: datetime | None = None


class Decide(BaseModel):
    approve: bool
    comment: str | None = Field(default=None, max_length=300)


READERS = {"super_admin", "consultant", "client_admin", "analyst", "viewer"}      # employees never see sends/releases


async def _extras(c, rows) -> dict:
    """Display facts for a page of approvals (who, which survey, which channels). One query per kind, never per row."""
    people = await users_repo.emails_by_id(c, list({x for r in rows for x in (r.proposed_by, r.decided_by) if x}))
    inv_ids, sids = [], []
    for r in rows:
        p = json.loads(r.payload)
        for key, bucket in (("invitation_id", inv_ids), ("survey_id", sids)):
            try:
                bucket.append(uuid.UUID(p[key]))
            except (KeyError, ValueError, TypeError):
                pass
    inv = {r.id: r for r in await invitations_repo.basics_for(c, inv_ids)} if inv_ids else {}
    titles = {r.id: json.loads(r.title).get("default") for r in await surveys_repo.titles_for(c, sids + [i.survey_id for i in inv.values()])}
    out = {}
    for r in rows:
        p = json.loads(r.payload)
        i = inv.get(uuid.UUID(p["invitation_id"])) if p.get("invitation_id") else None
        sid = i.survey_id if i else (uuid.UUID(p["survey_id"]) if p.get("survey_id") else None)
        out[r.id] = {"proposed_by_email": people.get(r.proposed_by), "decided_by_email": people.get(r.decided_by), "title": action_title(r.action_type),
                     "subtitle": action_subtitle(r.action_type, titles.get(sid), list(i.channels) if i else None, p)}
    return out


def _out(r, with_conf=True, extra=None):
    d = {"id": str(r.id), "action_type": r.action_type, "risk": r.risk, "status": r.status, "payload": json.loads(r.payload),
         "preview": json.loads(r.preview), "proposed_by": str(r.proposed_by) if r.proposed_by else None,
         "scheduled_for": r.scheduled_for.isoformat() if r.scheduled_for else None, "created_at": r.created_at.isoformat(),
         "receipt": json.loads(r.receipt) if r.receipt else None, "error": r.error}
    d["confirmation"] = confirmation(r.action_type, d["receipt"]) if with_conf else ""
    d["decision_comment"] = r.decision_comment
    d["decided_at"] = r.decided_at.isoformat() if r.decided_at else None
    d["executed_at"] = r.executed_at.isoformat() if r.executed_at else None
    d["recipients"] = d["preview"].get("will_receive")
    if extra:
        d.update(extra)
    return d


@router.post("", status_code=201)
async def propose(b: Propose, o: OrgCtx = Depends(org_ctx)):
    async with o.tx(WRITERS) as c:
        existing = await repo.by_idempotency_key(c, b.idempotency_key)
        if existing:
            return _out(existing)                                   # replay-safe
        payload, preview = dict(b.payload), {}
        if b.action_type in ("send_survey_invites", "send_reminder"):
            iid = payload.get("invitation_id")
            try:
                inv_id = uuid.UUID(iid)
            except (TypeError, ValueError):
                raise HTTPException(422, "payload.invitation_id required") from None
            inv = await invitations_repo.get(c, inv_id)
            if not inv:
                raise HTTPException(404, "invitation not found")
            if inv.status not in ("draft", "pending_approval"):
                raise HTTPException(409, "invitation already sent")
            preview = await audience_preview(c, inv.model_dump())
            if any(ch in ("sms", "whatsapp") for ch in inv.channels):
                from app.app.billing import require
                await require(c, "messages", preview["will_receive"])
            if preview["will_receive"] == 0:
                raise HTTPException(409, "audience is empty after consent, suppression and cooldown checks")
            await invitations_repo.reset_for_approval(c, inv_id)
        elif b.action_type == "launch_360_cycle":
            from app.app.routers.feedback360 import launch_preview
            try:
                cid = uuid.UUID(payload["cycle_id"])
            except (KeyError, ValueError, TypeError):
                raise HTTPException(422, "payload.cycle_id required") from None
            preview = await launch_preview(c, cid)
            if preview.get("blocked"):
                raise HTTPException(409, preview["blocked"])
        elif b.action_type == "start_conversations":
            from app.app.billing import require
            from app.app.routers.privacy import processor_on
            await processor_on(c, "whatsapp")
            await require(c, "messages")
            from app.app.audience import load_audience
            from app.core.conversation import ChatError, plan_turns
            try:
                sid = uuid.UUID(payload["survey_id"]); ch = payload["channel"]; lists = [uuid.UUID(x) for x in payload["list_ids"]]
            except (KeyError, ValueError, TypeError):
                raise HTTPException(422, "payload needs survey_id, channel, list_ids") from None
            if ch not in ("sms", "whatsapp") or not lists or len(lists) > 20:
                raise HTTPException(422, "bad channel or lists")
            d = await surveys_repo.latest_published_definition(c, sid)
            if d is None:
                raise HTTPException(409, "survey has no published version")
            try:
                plan_turns(json.loads(d))
            except ChatError as e:
                raise HTTPException(409, str(e)) from None
            _, (aud, _) = await load_audience(c, lists, [ch])
            if aud.will_receive == 0:
                raise HTTPException(409, "audience is empty after consent, suppression and cooldown checks")
            payload = {"survey_id": str(sid), "channel": ch, "list_ids": [str(x) for x in lists]}
            preview = {"will_receive": aud.will_receive, "channel": ch}
        elif b.action_type == "send_case_followup":
            try:
                cid = uuid.UUID(payload["case_id"]); msg = str(payload["message"]).strip()
            except (KeyError, ValueError, TypeError):
                raise HTTPException(422, "payload needs case_id and message") from None
            if not 1 <= len(msg) <= 1000:
                raise HTTPException(422, "message must be 1-1000 characters")
            case = await cases_repo.consent_of(c, cid)
            if case is None:
                raise HTTPException(404, "case not found")
            if case.kind != "respondent" or not case.consented:
                raise HTTPException(409, "respondent has not consented to follow-up")
            payload = {"case_id": str(cid), "message": msg}
            preview = {"case_id": str(cid), "message": msg}
        elif b.action_type == "publish_survey_version":
            try:
                sid, ver = uuid.UUID(payload["survey_id"]), int(payload["version"])
            except (KeyError, ValueError, TypeError):
                raise HTTPException(422, "payload needs survey_id and version") from None
            if not await surveys_repo.has_unpublished_version(c, sid, ver):
                raise HTTPException(409, "version not found or already published")
        aid = uuid.uuid4()
        await repo.insert(c, uuid.UUID(o.org_id), aid, b.action_type, RISK[b.action_type], json.dumps(payload),
                          json.dumps(preview), uuid.UUID(o.user_id), b.idempotency_key, b.scheduled_for)
        if b.action_type in ("send_survey_invites", "send_reminder"):
            await invitations_repo.link_approval(c, uuid.UUID(payload["invitation_id"]), aid)
        elif b.action_type == "launch_360_cycle":
            await cycles_repo.link_launch_approval(c, uuid.UUID(payload["cycle_id"]), aid)
        await repo.log_proposed(c, uuid.UUID(o.org_id), aid, uuid.UUID(o.user_id))
        return _out(await repo.get(c, aid))


@router.get("")
async def list_approvals(status: str = Query("pending", pattern="^(pending|approved|rejected|executed|failed|all)$"), o: OrgCtx = Depends(org_ctx)):
    async with o.tx(READERS) as c:
        rows = await repo.list_by_status(c, status)
        counts = await repo.counts_by_status(c)
        receipts = await repo.recent_executed(c)
        ex = await _extras(c, list(rows) + list(receipts))
    return {"counts": counts, "items": [_out(r, extra=ex[r.id]) for r in rows], "receipts": [_out(r, extra=ex[r.id]) for r in receipts], "can_decide": o.role in {"client_admin", "consultant", "super_admin"}}


@router.get("/{aid}")
async def get_approval(aid: uuid.UUID, o: OrgCtx = Depends(org_ctx)):
    async with o.tx(READERS) as c:
        r = await repo.get(c, aid)
        if not r:
            raise HTTPException(404, "not found")
        ev = await repo.events(c, aid)
        ex = (await _extras(c, [r]))[r.id]
    return _out(r, extra=ex) | {"events": [{"event": e.event, "actor": str(e.actor) if e.actor else None, "at": e.at.isoformat()} for e in ev]}


@router.post("/{aid}/decide")
async def decide_(aid: uuid.UUID, b: Decide, o: OrgCtx = Depends(org_ctx)):
    async with o.tx() as c:
        r = await repo.get_for_update(c, aid)
        if not r:
            raise HTTPException(404, "not found")
        try:
            d = decide(r.status, str(r.proposed_by) if r.proposed_by else None, o.user_id, o.role, r.risk, b.approve)
        except ApprovalError as e:
            raise HTTPException(409 if "already" in str(e) else 403, str(e)) from None
        await repo.record_decision(c, aid, d.status, uuid.UUID(o.user_id), b.comment)
        await repo.log_decision(c, uuid.UUID(o.org_id), aid, uuid.UUID(o.user_id), d.status, json.dumps({"comment": b.comment}))
        if d.status == "rejected" and r.action_type in ("send_survey_invites", "send_reminder"):
            await invitations_repo.back_to_draft(c, uuid.UUID(json.loads(r.payload)["invitation_id"]))
        job = None
        if d.status == "approved":
            job = await Q.enqueue(c, "run_approved", {"approval_id": str(aid)}, run_after=r.scheduled_for)
    return {"status": d.status, "job_id": job}
