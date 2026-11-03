"""The live check behind sensitive actions: GET {SUPABASE_URL}/auth/v1/user with the publishable key and the user's own token, uncached, 5 seconds. A clear "gone" is AuthError;
anything that is not a clear answer is AuthUnavailable, so those actions fail closed and are never allowed on a guess."""
import httpx
import pytest

from app.adapters.auth_supabase import LIVE_TIMEOUT, SupabaseAuth
from app.core.ports import AuthError, AuthUnavailable

BASE = "https://project.example.com/auth/v1"
KEY = "sb_publishable_testkey"


def auth(handler, **kw):
    return SupabaseAuth(BASE, BASE, "authenticated", apikey=KEY, transport=httpx.MockTransport(handler), **kw)


def answer(status, body=None):
    return lambda req: httpx.Response(status, json=body if body is not None else {"msg": "x"})


async def test_the_request_is_the_documented_one():
    seen: list[httpx.Request] = []

    def handler(req):
        seen.append(req)
        return httpx.Response(200, json={"id": "u"})
    a = auth(handler)
    await a.alive("user.jwt.token")
    r = seen[0]
    assert r.method == "GET" and str(r.url) == f"{BASE}/user"
    assert r.headers["apikey"] == KEY and r.headers["authorization"] == "Bearer user.jwt.token"          # the key in apikey, the user's token as the bearer, nothing else
    assert r.extensions["timeout"]["read"] == LIVE_TIMEOUT == 5.0 and r.extensions["timeout"]["connect"] == 5.0
    assert "cache-control" not in r.headers and "if-none-match" not in r.headers
    await a.aclose()


async def test_every_call_asks_again():
    n = 0

    def handler(req):
        nonlocal n
        n += 1
        return httpx.Response(200, json={})
    a = auth(handler)
    for _ in range(3):
        await a.alive("t")
    assert n == 3                                                                                       # no cache of the answer
    await a.aclose()


async def test_one_client_serves_every_check_and_is_closed_at_shutdown():
    a = auth(answer(200))
    assert a._live is None
    await a.alive("t")
    first = a._live
    await a.alive("t")
    assert a._live is first and not first.is_closed                                                     # reused, not made per call
    await a.aclose()
    assert first.is_closed and a._live is None
    await a.aclose()                                                                                    # closing twice is harmless
    await a.alive("t")                                                                                  # and it can be used again afterwards
    assert a._live is not first
    await a.aclose()


async def test_ok_means_the_session_is_good():
    assert await auth(answer(200)).alive("t") is None                                                   # the answer carried no list of factors: unknown, not zero


async def test_the_answer_also_counts_the_verified_authenticator_factors():
    body = {"factors": [{"status": "verified", "factor_type": "totp"}, {"status": "unverified", "factor_type": "totp"}]}
    assert await auth(answer(200, body)).alive("t") == 1
    assert await auth(answer(200, {"factors": []})).alive("t") == 0
    assert await auth(answer(200, {"factors": "x"})).alive("t") is None


@pytest.mark.parametrize("status", [400, 401, 403, 404, 405, 410, 422, 451])
async def test_a_4xx_verdict_means_the_session_is_gone(status):
    with pytest.raises(AuthError) as ei:
        await auth(answer(status)).alive("t")
    assert not isinstance(ei.value, AuthUnavailable)


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504, 301, 302])
async def test_try_later_server_trouble_and_oddities_are_unavailable_never_allowed(status):
    with pytest.raises(AuthUnavailable):
        await auth(answer(status)).alive("t")


@pytest.mark.parametrize("error", [httpx.ReadTimeout("slow"), httpx.ConnectTimeout("slow"), httpx.ConnectError("refused"), httpx.RemoteProtocolError("reset")])
async def test_timeouts_and_network_errors_are_unavailable(error):
    def handler(req):
        raise error
    with pytest.raises(AuthUnavailable):
        await auth(handler).alive("t")


async def test_the_key_and_token_are_in_nothing_that_is_raised_or_printed():
    a = auth(answer(500))
    with pytest.raises(AuthUnavailable) as ei:
        await a.alive("secret.user.token")
    assert "secret.user.token" not in str(ei.value) + repr(ei.value) + repr(a) and KEY not in str(ei.value) + repr(a)
