"""An administrator who has not passed two-step verification (aal1) must get no tenant data from any route. Probes every GET route without a path parameter."""
import pytest

from tests.integration.test_distribution_flow import invite_member

# Routes that answer at aal1 on purpose: user-level, health, or constant catalogues that carry no tenant data.
OPEN = {"/healthz", "/readyz", "/metrics", "/v1/me", "/v1/orgs", "/v1/security/sessions", "/v1/permissions", "/v1/presets", "/v1/question-types"}


def _probe_paths(app):
    for path, ops in app.openapi()["paths"].items():
        if "get" in ops and "{" not in path and not path.startswith(("/public", "/v1/platform", "/api/")):
            yield path, ops["get"]


def _query(op):
    def value(p):
        if p["name"].endswith("_id"):
            return "00000000-0000-4000-8000-000000000001"
        return "abc_key" if "pattern" in p.get("schema", {}) else "x"
    return {p["name"]: value(p) for p in op.get("parameters", []) if p["in"] == "query" and p.get("required")}


@pytest.mark.security
async def test_an_administrator_at_the_first_level_gets_no_tenant_data_from_any_get_route(make_user, client, app):
    a = make_user(); org = await a.create_org()
    seen, leaks = 0, []
    for path, op in _probe_paths(app):
        if path in OPEN:
            continue
        r = await client.get(path, params=_query(op), headers=a.headers(org, mfa=False)); seen += 1
        if not (r.status_code == 403 and r.json().get("detail", {}).get("code") == "mfa_required"):
            leaks.append((path, r.status_code))
    assert seen > 40, seen                                              # the probe really covered the API
    assert not leaks, leaks


@pytest.mark.security
async def test_a_required_role_chosen_by_the_organisation_is_covered_the_same_way(make_user, client, app):
    a, b = make_user(), make_user()
    org = await a.create_org(); await invite_member(client, a, org, b, role="analyst")
    await client.put("/v1/security/policy", json={"require_mfa_roles": ["analyst"], "reverify_sensitive": False}, headers=a.headers(org))
    bad = []
    for path, op in _probe_paths(app):
        if path in OPEN:
            continue
        r = await client.get(path, params=_query(op), headers=b.headers(org, mfa=False))
        if r.status_code == 200:
            bad.append(path)
    assert not bad, bad


@pytest.mark.security
async def test_a_required_role_that_never_enrolled_gets_no_tenant_data_once_the_grace_is_over(make_user, client, app):
    from tests.integration.test_mfa_grace import end_grace
    a = make_user(); org = await a.create_org(mfa=False)
    assert (await client.get("/v1/surveys", headers=a.headers(org, mfa=False))).status_code == 200          # inside the grace the first level works
    await end_grace(org, a)
    leaks = []
    for path, op in _probe_paths(app):
        if path in OPEN:
            continue
        r = await client.get(path, params=_query(op), headers=a.headers(org, mfa=False))
        if not (r.status_code == 403 and r.json().get("detail", {}).get("code") == "mfa_required"):
            leaks.append((path, r.status_code))
    assert not leaks, leaks
