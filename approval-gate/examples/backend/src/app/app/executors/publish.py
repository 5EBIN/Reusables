import uuid

from app.db.repos import surveys


async def execute(conn, notifier, approval: dict, base_url: str, now=None) -> dict:
    p = approval["payload"]
    sid, ver = uuid.UUID(p["survey_id"]), int(p["version"])
    await surveys.ensure_published(conn, sid, ver)
    return {"survey_id": p["survey_id"], "version": ver}
