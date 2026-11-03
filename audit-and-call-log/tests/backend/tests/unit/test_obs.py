import pytest

from app.core.obs import Registry, hash_ref, route_label, scrub


@pytest.mark.parametrize("path,exp", [("/v1/surveys/3f2c1d8e-9a4b-4c1e-8d2f-0a1b2c3d4e5f/summary", "/v1/surveys/:id/summary"), ("/public/v1/c/" + "A" * 43 + "/responses", "/public/v1/c/:token/responses"),
                                      ("/v1/me", "/v1/me")])
def test_route_label_collapses_ids_and_tokens(path, exp):
    assert route_label(path) == exp


def test_scrub_and_hash():
    d = scrub({"Authorization": "Bearer x", "password": "p", "otp": "1", "session_token": "t", "status": 200, "route": "/x"})
    assert d["Authorization"] == d["password"] == d["otp"] == d["session_token"] == "[redacted]" and d["status"] == 200
    assert hash_ref(None) is None and len(hash_ref("a")) == 12 and hash_ref("a") != hash_ref("b")


def test_registry_render_buckets():
    r = Registry()
    r.observe("GET", "/v1/surveys/3f2c1d8e-9a4b-4c1e-8d2f-0a1b2c3d4e5f", 200, 0.03)
    r.observe("GET", "/v1/surveys/3f2c1d8e-9a4b-4c1e-8d2f-0a1b2c3d4e5f", 503, 3.0)
    out = r.render()
    assert 'route="/v1/surveys/:id",status="2xx"} 1' in out and 'status="5xx"} 1' in out and 'le="0.05"} 1' in out and 'le="+Inf"} 1' in out and "3f2c1d8e" not in out
