import hashlib
import json
import secrets
import uuid
from datetime import datetime
from typing import Any, Literal

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.app.access import can_edit
from app.app.audit import audit
from app.app.deps import OrgCtx, org_ctx
from app.core.logic import compile_rules
from app.core.sanitize import clean_definition
from app.core.studio import completeness, etag
from app.core.survey_schema import DefinitionError, validate_definition
from app.db.repos import collectors as collectors_repo
from app.db.repos import surveys as repo

router = APIRouter(prefix="/v1", tags=["surveys"])
WRITERS = {"client_admin", "consultant", "super_admin", "analyst"}


def hash_token(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


class NewSurvey(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    title: dict[str, str] = Field(min_length=1)


class DefBody(BaseModel):
    definition: dict[str, Any]


class NewCollector(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    kind: Literal["link", "kiosk"] = "link"
    expires_at: datetime | None = None
    version: int | None = Field(default=None, ge=1)


@router.post("/surveys", status_code=201)
async def create_survey(b: NewSurvey, o: OrgCtx = Depends(org_ctx)):
    if "default" not in b.title or any(len(v) > 300 for v in b.title.values()):
        raise HTTPException(422, "title needs 'default' (<=300 chars)")
    async with o.tx(WRITERS) as c:
        oid = uuid.UUID(o.org_id)
        if await repo.insert(c, oid, b.id, json.dumps(b.title, ensure_ascii=False), uuid.UUID(o.user_id)):
            await repo.add_owner(c, oid, b.id, uuid.UUID(o.user_id))
            await audit(c, o, "survey.created", str(b.id))
    return {"id": str(b.id)}


@router.get("/surveys")
async def list_surveys(status: Literal["all", "live", "draft", "closed"] = "all", language: str = "", owner: uuid.UUID | None = None, q: str = "",
                       limit: int = 100, offset: int = 0, o: OrgCtx = Depends(org_ctx)):
    limit = max(1, min(limit, 200))
    async with o.tx() as c:
        rows = await repo.list_rows(c)
        spark = {}
        for r in await repo.response_spark(c):
            spark.setdefault(r.survey_id, []).append({"date": r.d.isoformat(), "n": r.n})
        team = {}
        for r in await repo.collaborators(c):
            team.setdefault(r.survey_id, []).append({"user_id": str(r.user_id), "email": r.email, "role": r.role})
    today = datetime.now().date()
    out = []
    for r in rows:
        closed = r.closed_at is not None or (r.closes_on is not None and r.closes_on < today)
        st = "closed" if closed else "live" if r.published else "draft"
        langs = sorted(set(r.langs or []) | {"en"})
        t = json.loads(r.title)
        members = team.get(r.id, [])
        if (status != "all" and st != status) or (language and language not in langs) or (owner and str(owner) not in {m["user_id"] for m in members if m["role"] == "owner"}):
            continue
        if q and q.lower() not in " ".join(t.values()).lower():
            continue
        qs = sum(1 for p in json.loads(r.defn or '{"pages":[]}')["pages"] for _ in p["elements"]) if r.defn else 0
        out.append({"id": str(r.id), "title": t, "status": st, "languages": langs, "version": r.latest, "questions": qs, "responses": r.n,
                    "completion": round(100 * r.done / r.n) if r.n else None, "last_14_days": spark.get(r.id, []), "team": members,
                    "updated_at": r.updated_at.isoformat(), "created_at": r.created_at.isoformat()})
    return {"total": len(out), "items": out[offset:offset + limit]}


@router.get("/surveys/{sid}")
async def get_survey(sid: uuid.UUID, o: OrgCtx = Depends(org_ctx)):
    async with o.tx() as c:
        s = await repo.head(c, sid)
        if not s:
            raise HTTPException(404, "not found")
        vs = await repo.versions(c, sid)
    return {"id": str(sid), "title": json.loads(s.title),
            "versions": [{"version": v.version, "published": v.published_at is not None, "languages": v.languages} for v in vs]}


@router.put("/surveys/{sid}/versions/{n}")
async def put_version(sid: uuid.UUID, n: int, b: DefBody, o: OrgCtx = Depends(org_ctx), if_match: str | None = Header(default=None)):
    """Create or replace draft version n (idempotent, optimistic concurrency via If-Match etag). Published versions are immutable."""
    if n < 1:
        raise HTTPException(422, "bad version")
    defn = clean_definition(b.definition)
    built = compile_rules(defn) if isinstance(defn, dict) and isinstance(defn.get("pages"), list) else None
    try:
        if built is not None and built.errors:
            raise DefinitionError("; ".join(built.errors))
        defn = built.definition if built is not None else defn
        comp = validate_definition(defn)
    except DefinitionError as e:
        raise HTTPException(422, str(e)) from None
    async with o.tx(WRITERS) as c:
        if not await repo.exists(c, sid):
            raise HTTPException(404, "not found")
        if not await can_edit(c, o, sid):
            raise HTTPException(403, "forbidden")
        latest = await repo.latest_version(c, sid)
        if n > latest + 1:
            raise HTTPException(422, "version must be <= latest+1")
        cur = await repo.version_definition(c, sid, n)
        if cur is not None and if_match and if_match.strip('"') != etag(json.loads(cur)):
            raise HTTPException(409, {"code": "conflict", "etag": etag(json.loads(cur)), "definition": json.loads(cur)})
        try:
            await repo.upsert_version(c, uuid.UUID(o.org_id), sid, n, json.dumps(defn, ensure_ascii=False), comp.languages, uuid.UUID(o.user_id))
        except asyncpg.PostgresError as e:
            if getattr(e, "sqlstate", "") == "55000":
                raise HTTPException(409, "published versions are immutable") from None
            raise
        await repo.touch(c, sid)
    return {"version": n, "languages": comp.languages, "etag": etag(defn), "completeness": completeness(defn), "definition": defn}


@router.post("/surveys/{sid}/versions/{n}/publish")
async def publish(sid: uuid.UUID, n: int, o: OrgCtx = Depends(org_ctx)):
    async with o.tx(WRITERS) as c:
        found, published_at = await repo.version_published_at(c, sid, n)
        if not found:
            raise HTTPException(404, "not found")
        if not await can_edit(c, o, sid):
            raise HTTPException(403, "forbidden")
        if published_at is None:
            if o.request.app.state.container.require_approval_for_publish:
                raise HTTPException(409, "approval required: propose publish_survey_version")
            await repo.publish_version(c, sid, n)
            await audit(c, o, "survey.published", str(sid), {"version": n})
    return {"version": n, "published": True}


@router.post("/surveys/{sid}/collectors", status_code=201)
async def create_collector(sid: uuid.UUID, b: NewCollector, o: OrgCtx = Depends(org_ctx)):
    async with o.tx(WRITERS) as c:
        if not await repo.exists(c, sid):
            raise HTTPException(404, "not found")
        if not await can_edit(c, o, sid):
            raise HTTPException(403, "forbidden")
        if await collectors_repo.exists(c, b.id):
            return {"id": str(b.id), "token": None, "note": "token is shown only once"}
        if not await collectors_repo.count_published(c, sid, b.version):
            raise HTTPException(409, "no published version")
        token = secrets.token_urlsafe(32)
        await collectors_repo.insert(c, uuid.UUID(o.org_id), b.id, sid, b.version, b.kind, hash_token(token), b.expires_at)
    return {"id": str(b.id), "token": token}


@router.post("/collectors/{cid}/revoke")
async def revoke(cid: uuid.UUID, o: OrgCtx = Depends(org_ctx)):
    async with o.tx(WRITERS) as c:
        matched = await collectors_repo.revoke(c, cid)
    if not matched:
        raise HTTPException(404, "not found")
    return {"revoked": True}
