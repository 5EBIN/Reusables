"""Quality & anomalies: editable rules, deterministic evaluation, reversible exclusions, flags per day."""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.app.audit import audit
from app.app.deps import OrgCtx, org_ctx
from app.app.routers.surveys import WRITERS
from app.core.quality import RuleError, evaluate, should_exclude, validate_rules
from app.db.repos import answers as answers_repo
from app.db.repos import quality_rules as rules_repo
from app.db.repos import responses as responses_repo
from app.db.repos import surveys as surveys_repo

router = APIRouter(prefix="/v1/surveys/{sid}/quality", tags=["quality"])
AUTO = "quality:"


async def _rules(c, sid):
    r = await rules_repo.get(c, sid)
    return validate_rules(json.loads(r) if isinstance(r, str) else (r or {}))


async def _check(c, sid):
    if not await surveys_repo.exists(c, sid):
        raise HTTPException(404, "not found")


@router.get("/rules")
async def get_rules(sid: uuid.UUID, o: OrgCtx = Depends(org_ctx)):
    async with o.tx(WRITERS) as c:
        await _check(c, sid)
        return await _rules(c, sid)


@router.put("/rules")
async def put_rules(sid: uuid.UUID, body: dict, o: OrgCtx = Depends(org_ctx)):
    try:
        rules = validate_rules(body)
    except RuleError as e:
        raise HTTPException(422, str(e)) from None
    async with o.tx(WRITERS) as c:
        await _check(c, sid)
        await rules_repo.upsert(c, uuid.UUID(o.org_id), sid, json.dumps(rules))
        await audit(c, o, "quality.rules", str(sid))
        return rules


async def _inputs(c, sid, rules):
    d = json.loads(await surveys_repo.latest_definition(c, sid))
    qs = [e for p in d["pages"] for e in p["elements"]]
    rating = {e["name"] for e in qs if e["type"] in ("rating", "slider")}
    matrix = {e["name"] for e in qs if e["type"] == "matrix"}
    text = {e["name"] for e in qs if e["type"] in ("text", "comment")}
    att = rules["attention"].get("question")
    rows = await responses_repo.completed_for_quality(c, sid)
    ans = await answers_repo.values_for_responses(c, [r.id for r in rows])
    by: dict = {}
    for a in ans:
        by.setdefault(a.response_id, []).append(a)
    out = []
    for r in rows:
        a = by.get(r.id, [])
        ratings = [x.value_num for x in a if x.question_id in rating and x.value_num is not None] + [x.value_choice for x in a if x.question_id in matrix]
        out.append({"id": str(r.id), "secs": (r.completed_at - r.started_at).total_seconds() if r.started_at else None, "device": r.device_hash, "ratings": ratings,
                    "texts": [x.value_text for x in a if x.question_id in text and x.value_text],
                    "attn": next((x.value_choice if x.value_choice is not None else x.value_num for x in a if x.question_id == att), None), "at": r.received_at})
    return out


@router.post("/run")
async def run(sid: uuid.UUID, o: OrgCtx = Depends(org_ctx)):
    """Recompute flags. Auto-exclusions are marked 'quality:<rule>' so they can be reversed; manual exclusions are never touched."""
    async with o.tx(WRITERS) as c:
        await _check(c, sid)
        rules = await _rules(c, sid)
        flags = evaluate(await _inputs(c, sid, rules), rules)
        ids = await responses_repo.quality_states(c, sid)
        flagged = excluded = 0
        for r in ids:
            f = flags.get(str(r.id), [])
            kept_manual = [x for x in r.quality_flags if not x.startswith("auto:")]
            new_flags = sorted(set(kept_manual) | {f"auto:{x}" for x in f})
            why = should_exclude(f, rules)
            was_auto = bool(r.exclude_reason and r.exclude_reason.startswith(AUTO))
            if r.excluded and not was_auto:
                ex, reason = True, r.exclude_reason                      # manual exclusion wins
            elif why:
                ex, reason = True, AUTO + why
            else:
                ex, reason = False, None
            await responses_repo.set_quality(c, r.id, new_flags, ex, reason)
            flagged += bool(f); excluded += ex
        await audit(c, o, "quality.run", str(sid), {"flagged": flagged, "excluded": excluded})
        return {"responses": len(ids), "flagged": flagged, "excluded": excluded}


@router.get("/summary")
async def summary(sid: uuid.UUID, o: OrgCtx = Depends(org_ctx)):
    async with o.tx(WRITERS) as c:
        await _check(c, sid)
        rules = await _rules(c, sid)
        total = await responses_repo.count_all(c, sid)
        per_rule = await responses_repo.auto_flag_counts(c, sid)
        exc = await responses_repo.count_excluded(c, sid)
        flagged = await responses_repo.count_flagged(c, sid)
        days = await responses_repo.flagged_per_day(c, sid)
        med = await responses_repo.median_seconds_kept(c, sid)
        flag_only = await responses_repo.count_flagged_not_excluded(c, sid)
        med_all = await responses_repo.median_seconds_all(c, sid)
        return {"flag_only": flag_only, "median_seconds_all": round(med_all) if med_all is not None else None, "flagged": flagged, "flagged_pct": round(100 * flagged / total, 1) if total else 0, "excluded": exc, "median_seconds_kept": round(med) if med is not None else None,
                "rules": [{"rule": k, **v, "flagged": per_rule.get(k, 0), "params": {f: x for f, x in v.items() if f != "treatment"}} for k, v in rules.items()], "per_day": [{"day": r.d.isoformat(), "flags": r.n} for r in days], "method": "rule-based"}
