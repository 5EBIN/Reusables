import uuid

import pytest

from app.db import tenant_tx
from tests.integration.test_distribution_flow import invite_member
from tests.integration.test_semantic import base, embedded, frozen_taxonomy

pytestmark = pytest.mark.asyncio


async def counts(app, org, rid):
    async with tenant_tx(app.state.pool, None, org) as c:
        return {t: await c.fetchval(f"select count(*) from {t} where response_id=$1", rid)
                for t in ("text_embeddings", "semantic_cluster_members", "theme_assignments")}


async def erase(client, h, rid, second):
    d = (await client.post("/v1/privacy/dsr", json={"type": "erase_respondent", "subject": str(rid)}, headers=h)).json()["id"]
    assert (await client.post(f"/v1/privacy/dsr/{d}/verify", json={"note": "verified by email reply"}, headers=second)).status_code == 200
    r = await client.post(f"/v1/privacy/dsr/{d}/complete", headers=h)
    assert r.status_code == 200, r.text


async def test_respondent_erasure_removes_semantic_rows_and_label_references(make_user, client, app):
    u, org, h, sid = await embedded(make_user, client)
    b = make_user(); await invite_member(client, u, org, b); second = b.headers(org)
    await client.post(base(sid) + "/cluster", json={}, headers=h)
    await frozen_taxonomy(app, client, h, sid)
    await client.post(base(sid) + "/assign", json={}, headers=h)
    async with tenant_tx(app.state.pool, None, org) as c:
        rid = await c.fetchval("select response_id from text_embeddings limit 1")
        other = await c.fetchval("select response_id from text_embeddings where response_id <> $1 limit 1", rid)
    before = await counts(app, org, rid)
    assert before["text_embeddings"] >= 1 and before["semantic_cluster_members"] >= 1
    await erase(client, h, rid, second)
    assert await counts(app, org, rid) == {"text_embeddings": 0, "semantic_cluster_members": 0, "theme_assignments": 0}
    assert (await counts(app, org, other))["text_embeddings"] >= 1                                   # other respondents untouched
    async with tenant_tx(app.state.pool, None, org) as c:
        assert await c.fetchval("select count(*) from semantic_cluster_labels where $1 = any(verbatim_ids)", rid) == 0
    d2 = (await client.post("/v1/privacy/dsr", json={"type": "erase_respondent", "subject": str(rid)}, headers=h)).json()["id"]     # already erased: still fine
    await client.post(f"/v1/privacy/dsr/{d2}/verify", json={"note": "verified by email reply"}, headers=second)
    assert (await client.post(f"/v1/privacy/dsr/{d2}/complete", headers=h)).status_code == 200


@pytest.mark.security
async def test_erasure_function_is_org_scoped_and_api_still_cannot_delete(make_user, client, app):
    import asyncpg
    u, org, h, sid = await embedded(make_user, client)
    v, org2, h2, sid2 = await embedded(make_user, client)
    async with tenant_tx(app.state.pool, None, org) as c:
        rid = await c.fetchval("select response_id from text_embeddings limit 1")
    async with tenant_tx(app.state.pool, None, org2) as c:
        assert await c.fetchval("select app.erase_semantic_for_response($1)", rid) == 0                 # another org's session cannot erase it
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await c.execute("delete from text_embeddings")
    assert (await counts(app, org, rid))["text_embeddings"] >= 1
    async with app.state.pool.acquire() as c:
        with pytest.raises(asyncpg.PostgresError):
            await c.fetchval("select app.erase_semantic_for_response($1)", uuid.uuid4())                  # no org context: refused
