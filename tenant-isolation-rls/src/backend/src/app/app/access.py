"""Survey-level access: org HR roles always; otherwise collaborator role; legacy surveys without collaborators fall back to org writer roles."""
import uuid

HR = {"client_admin", "consultant", "super_admin"}
WRITERS = {"client_admin", "consultant", "super_admin", "analyst"}


async def survey_role(c, o, sid: uuid.UUID) -> str | None:
    if o.role in HR:
        return "owner"
    r = await c.fetchval("select role from survey_collaborators where survey_id=$1 and user_id=$2", sid, uuid.UUID(o.user_id))
    if r:
        return r
    n = await c.fetchval("select count(*) from survey_collaborators where survey_id=$1", sid)
    return "editor" if n == 0 and o.role in WRITERS else None


async def can_edit(c, o, sid: uuid.UUID) -> bool:
    return await survey_role(c, o, sid) in ("owner", "editor")
