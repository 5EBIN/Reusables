"""Append-only, hash-chained audit trail helper (hash computed by a DB trigger)."""
import json


async def audit(c, o, action: str, target: str | None = None, detail: dict | None = None, on_behalf_of: str | None = None) -> None:
    if getattr(o, "impersonator", ""):
        return                                    # support sessions are read-only; the session start is already audited under both identities
    label = await c.fetchval("select email from users where id=$1", __import__("uuid").UUID(o.user_id))
    await c.execute("insert into audit_log(org_id,actor,actor_label,on_behalf_of,action,target,detail) values($1,$2,$3,$4,$5,$6,$7)",
                    __import__("uuid").UUID(o.org_id), __import__("uuid").UUID(o.user_id), label, on_behalf_of, action, target, json.dumps(detail or {}, ensure_ascii=False))
