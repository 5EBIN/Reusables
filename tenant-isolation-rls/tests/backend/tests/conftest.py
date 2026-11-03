from tests.dsn import API as API_DSN, OWNER as OWNER_DSN
import os
import uuid

import httpx
import pytest

os.environ["APP_ENV"] = "test"                         # production guard OFF under tests (it defaults to production when unset)
os.environ.setdefault("DATABASE_URL", API_DSN)
os.environ.setdefault("RATE_LIMIT", "1000")
os.environ.setdefault("AI_RATE_PER_MINUTE", "1000")            # the per-minute AI limits are tested with small ones in test_ai_rate_limit.py
os.environ.setdefault("AI_RATE_PER_MINUTE_ORG", "5000")
os.environ["STORE_ROOT"] = "/tmp/app-test-store"
os.environ.setdefault("STAFF_REQUIRE_MFA", "false")        # security tests turn it on explicitly
os.environ.setdefault("DEFAULT_PLAN", "business")      # orgs without a subscription row; billing tests switch plans explicitly

from app.app.main import create_app  # noqa: E402


def pytest_collection_modifyitems(config, items):
    """Marks by location so `-m integration` / `-m "not live"` work without editing every test: tests/integration, tests/regression, and the golden-set checks."""
    for item in items:
        parts = item.path.parts
        if "integration" in parts:
            item.add_marker(pytest.mark.integration)
        if "regression" in parts:
            item.add_marker(pytest.mark.regression)
        if "golden" in item.name:
            item.add_marker(pytest.mark.golden)
        if item.get_closest_marker("live") and os.environ.get("EVAL_LIVE") != "1":
            item.add_marker(pytest.mark.skip(reason="live test: set EVAL_LIVE=1 and a key"))


@pytest.fixture(scope="session")
async def app():
    a = create_app()
    async with a.router.lifespan_context(a):
        yield a


@pytest.fixture(scope="session")
async def client(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        yield c


class User:
    def __init__(self, app, client, email=None):
        self.app, self.client = app, client
        self.email = email or f"u{uuid.uuid4().hex[:8]}@example.com"
        self.sub = f"fake|{uuid.uuid4().hex[:10]}"

    def headers(self, org=None, **kw):
        kw.setdefault("mfa", True)                       # tests act as users who completed two-step verification (aal2); security tests pass mfa=False
        h = {"Authorization": "Bearer " + self.app.state.container.auth.make_token(self.sub, self.email, **kw)}
        if org:
            h["X-Org-Id"] = str(org)
        return h

    async def create_org(self, name="Org", **kw):
        oid = uuid.uuid4()
        r = await self.client.post("/v1/orgs", json={"id": str(oid), "name": name}, headers=self.headers(**kw))
        assert r.status_code == 201, r.text
        return str(oid)


@pytest.fixture
def make_user(app, client):
    return lambda **kw: User(app, client, **kw)


@pytest.fixture
def make_staff(app, client):
    """Marks a user as Acme platform staff via the owner connection (there is deliberately no API for this)."""
    import asyncpg

    async def _go(user, role="support"):
        await user.create_org("staff-home")
        conn = await asyncpg.connect(OWNER_DSN)
        try:
            await conn.execute("insert into platform_staff(user_id, role) select user_id, $2 from identities where subject=$1 on conflict do nothing", user.sub, role)
        finally:
            await conn.close()
        return user
    return _go
