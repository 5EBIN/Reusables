"""Row-level security on users and identities: a user sees their own rows, an organisation's members see each other, nobody else is visible, and the runtime role
cannot write either table (first-call provisioning and the SSO email lookup go through definer functions)."""
import asyncio
import uuid

import asyncpg
import pytest

from app.db import tenant_tx
from app.db.repos import users as users_repo
from tests.integration.test_distribution_flow import invite_member


async def uid(client, u):
    return (await client.get("/v1/me", headers=u.headers())).json()["user_id"]


async def visible(app, user, org=None) -> set[str]:
    async with tenant_tx(app.state.pool, user, org) as c:
        return {str(r["id"]) for r in await c.fetch("select id from users")}


@pytest.mark.security
async def test_a_user_reads_only_their_own_row_without_an_organisation(make_user, client, app):
    a, b = make_user(), make_user()
    ia, ib = await uid(client, a), await uid(client, b)
    assert await visible(app, ia) == {ia}                                                    # not b, not anyone else
    assert await visible(app, ib) == {ib}
    async with tenant_tx(app.state.pool, ia, None) as c:
        assert [str(r["user_id"]) for r in await c.fetch("select user_id from identities")] == [ia]


@pytest.mark.security
async def test_members_see_each_other_but_not_other_organisations(make_user, client, app):
    admin, member, outsider, other_admin = make_user(), make_user(), make_user(), make_user()
    org = await admin.create_org(); other = await other_admin.create_org()
    await invite_member(client, admin, org, member, role="viewer")
    ia, im, io, ioa = [await uid(client, u) for u in (admin, member, outsider, other_admin)]
    assert await visible(app, ia, org) == {ia, im}                                           # admin sees the members of their organisation
    assert await visible(app, im, org) == {ia, im}                                           # so does an ordinary member (people lists, "edited by")
    assert await visible(app, ioa, other) == {ioa}
    assert await visible(app, io, org) == {io}                                               # naming an organisation you do not belong to reveals nobody
    assert await visible(app, ia, other) == {ia}


@pytest.mark.security
async def test_support_staff_see_the_members_while_viewing_an_organisation(make_user, make_staff, client, app):
    admin = make_user(); org = await admin.create_org()
    staff = await make_staff(make_user())
    ia, istaff = await uid(client, admin), await uid(client, staff)
    assert await visible(app, istaff, org) == {ia, istaff}


@pytest.mark.security
async def test_the_runtime_role_cannot_write_users_or_identities(make_user, client, app):
    ia = await uid(client, make_user())
    async with app.state.pool.acquire() as c:
        for sql in ("insert into users(id,email) values (gen_random_uuid(),'user@example.com')", "update users set email='user@example.com'",
                    "insert into identities(user_id,issuer,subject) values (gen_random_uuid(),'i','s')", "update identities set subject='s'"):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await c.execute(sql)
        assert not await c.fetch("select * from users")                                      # no tenant context: nothing is readable either
    assert ia


async def test_provisioning_is_idempotent_and_race_safe(app):
    iss, sub, email = "https://stub.example/auth/v1", f"sub-{uuid.uuid4().hex}", f"{uuid.uuid4().hex[:8]}@example.com"
    async def call():
        async with app.state.pool.acquire() as c:
            return await users_repo.provision(c, iss, sub, email)
    ids = await asyncio.gather(*(call() for _ in range(8)))
    assert len(set(ids)) == 1
    async with app.state.pool.acquire() as c:
        assert await users_repo.provision(c, iss, sub, "user@example.com") == ids[0]       # a later call links to the same row
    async with tenant_tx(app.state.pool, str(ids[0]), None) as c:
        assert await c.fetchval("select count(*) from users") == 1 and await c.fetchval("select email from users") == email


async def test_the_sso_email_lookup_works_without_reading_users(make_user, client, app):
    u = make_user(); await uid(client, u)
    async with tenant_tx(app.state.pool, None, None) as c:
        assert await users_repo.identity_user_id_by_email(c, u.email) is not None
        assert await users_repo.identity_user_id_by_email(c, "user@example.com") is None
