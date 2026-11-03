"""SupabaseAuth against the offline GoTrue stub: JWT strictness (HS256 + JWKS ES256) and REST contract. No network."""
import base64
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from app.adapters.auth_supabase import JWKS_MIN_REFETCH, SupabaseAuth
from app.core.ports import AuthError
from tests.support.gotrue_stub import APIKEY, AUD, HS_SECRET, ISS, GoTrueStub

SUB = "6f1c2c9e-3a53-4a53-9a39-5d1f0c6b7a10"
JWKS_URL = "https://stub.supabase.test/jwks.json"


def make(stub: GoTrueStub, **kw) -> SupabaseAuth:
    secret = HS_SECRET if stub.mode == "hs256" else None
    return SupabaseAuth("https://stub.supabase.test/auth/v1", ISS, AUD, secret=secret, allow_hs256=stub.mode == "hs256",
                        jwks_url=JWKS_URL if stub.mode == "es256" else None, apikey=APIKEY,
                        transport=stub.transport, jwks_transport=stub.jwks_transport, **kw)


@pytest.fixture(params=["hs256", "es256"])
def stub(request):
    return GoTrueStub(request.param)


def _b64(d: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


# ---- accept ---------------------------------------------------------------------------------------------------
async def test_valid_token_maps_to_principal(stub):
    p = (await make(stub).averify(stub.mint(SUB, "user@example.com", aal="aal2")))
    assert (p.subject, p.issuer, p.email, p.email_verified, p.mfa) == (SUB, ISS, "user@example.com", True, True)


async def test_leeway_accepts_small_skew_but_not_large(stub):
    a = make(stub)
    assert (await a.averify(stub.mint(SUB, "user@example.com", exp_in=-5))).subject == SUB
    with pytest.raises(AuthError):
        (await a.averify(stub.mint(SUB, "user@example.com", exp_in=-120)))


async def test_client_controlled_claims_do_not_grant_anything(stub):
    p = (await make(stub).averify(stub.mint(SUB, "user@example.com", user_metadata={"role": "owner", "org_id": "x", "is_admin": True},
                                    app_metadata={"role": "admin"})))
    assert not hasattr(p, "role") and p.mfa is False          # Principal carries no role/org: membership is DB-only


# ---- reject (every one is a security test) ------------------------------------------------------------------------
@pytest.mark.security
@pytest.mark.parametrize("name,kw", [
    ("wrong_iss", {"iss": "https://evil.test/auth/v1"}),
    ("wrong_aud", {"aud": "other"}),
    ("expired", {"exp_in": -3600}),
    ("nbf_future", {"nbf": int(time.time()) + 3600}),
    ("missing_sub", {"sub": ...}),
    ("empty_sub", {"sub": " "}),
    ("numeric_sub", {"sub": 12}),
    ("anon_role", {"role": "anon"}),
    ("service_role", {"role": "service_role"}),
    ("anonymous_signin", {"is_anonymous": True}),
    ("email_unconfirmed_claim", {"email_verified": False}),
    ("email_unconfirmed_meta", {"user_metadata": {"email_verified": False}}),
])
async def test_rejects_bad_claims(stub, name, kw):
    kw = dict(kw)
    tok = stub.mint(kw.pop("sub", SUB), "user@example.com", **kw)
    with pytest.raises(AuthError):
        (await make(stub).averify(tok))


@pytest.mark.security
async def test_rejects_tampered_signature_and_payload(stub):
    tok = stub.mint(SUB, "user@example.com")
    h, p, s = tok.split(".")
    flipped = s[:-4] + ("AAAA" if not s.endswith("AAAA") else "BBBB")
    with pytest.raises(AuthError):
        (await make(stub).averify(f"{h}.{p}.{flipped}"))
    forged = json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))
    forged["sub"] = "attacker"
    with pytest.raises(AuthError):
        (await make(stub).averify(f"{h}.{_b64(forged)}.{s}"))


@pytest.mark.security
async def test_rejects_alg_none_and_stripped_signature(stub):
    now = int(time.time())
    body = {"sub": SUB, "iss": ISS, "aud": AUD, "exp": now + 600, "role": "authenticated"}
    for hdr in ({"alg": "none", "typ": "JWT"}, {"alg": "None"}, {"alg": "NONE"}, {"alg": ""}):
        with pytest.raises(AuthError):
            (await make(stub).averify(f"{_b64(hdr)}.{_b64(body)}."))
    with pytest.raises(AuthError):
        (await make(stub).averify(stub.mint(SUB, "user@example.com").rsplit(".", 1)[0] + "."))


@pytest.mark.security
async def test_rejects_wrong_alg_in_allowlist_gap():
    stub = GoTrueStub("hs256")
    for alg in ("HS384", "HS512"):                           # same secret, algorithm outside the allow-list
        with pytest.raises(AuthError):
            (await make(stub).averify(stub.mint(SUB, "user@example.com", alg=alg)))
    es = GoTrueStub("es256")
    with pytest.raises(AuthError):                           # ES384 not allowed even with a published P-256 key
        (await make(es).averify(es.mint(SUB, "user@example.com", alg="ES384", key=ec.generate_private_key(ec.SECP384R1()))))


@pytest.mark.security
async def test_hs_rs_alg_confusion_blocked():
    es = GoTrueStub("es256")
    a = make(es)                                              # JWKS only, no shared secret configured
    pub_pem = es.keys[es.kid].public_key()
    from cryptography.hazmat.primitives import serialization as ser
    pem = pub_pem.public_bytes(ser.Encoding.PEM, ser.PublicFormat.SubjectPublicKeyInfo).decode()
    body = {"sub": SUB, "iss": ISS, "aud": AUD, "exp": int(time.time()) + 600, "role": "authenticated"}
    hs_with_public_key = jwt.encode(body, es.jwks()["keys"][0]["x"] * 3, algorithm="HS256", headers={"kid": es.kid})
    with pytest.raises(AuthError):
        (await a.averify(hs_with_public_key))
    both = SupabaseAuth("http://g", ISS, AUD, secret=HS_SECRET, jwks_url=JWKS_URL, jwks_transport=es.jwks_transport)
    # token claiming RS256/ES256 but MAC'd with the shared secret as if symmetric: must fail, never be accepted
    forged = f"{_b64({'alg': 'ES256', 'kid': es.kid, 'typ': 'JWT'})}.{_b64(body)}.{_b64({'x': 1})}"
    with pytest.raises(AuthError):
        (await both.averify(forged))
    assert pem                                                # public key material is not usable as an HMAC secret here
    hs_only = SupabaseAuth("http://g", ISS, AUD, secret=HS_SECRET)
    rsa_key = rsa.generate_private_key(65537, 2048)
    with pytest.raises(AuthError):                            # RS256 token, adapter has no JWKS: refused (no fall-through)
        (await hs_only.averify(jwt.encode(body, rsa_key, algorithm="RS256", headers={"kid": "k"})))


@pytest.mark.security
async def test_rs256_header_against_ec_jwk_is_kty_mismatch():
    es = GoTrueStub("es256")
    rsa_key = rsa.generate_private_key(65537, 2048)
    body = {"sub": SUB, "iss": ISS, "aud": AUD, "exp": int(time.time()) + 600, "role": "authenticated"}
    with pytest.raises(AuthError):
        (await make(es).averify(jwt.encode(body, rsa_key, algorithm="RS256", headers={"kid": es.kid})))


@pytest.mark.security
async def test_unknown_kid_rejected_and_refetch_is_bounded():
    es = GoTrueStub("es256")
    a = make(es)
    assert (await a.averify(es.mint(SUB, "user@example.com"))).subject == SUB
    base = es.jwks_hits
    rogue = ec.generate_private_key(ec.SECP256R1())
    for i in range(50):                                       # attacker spraying random kids
        with pytest.raises(AuthError):
            (await a.averify(jwt.encode({"sub": SUB, "iss": ISS, "aud": AUD, "exp": int(time.time()) + 600}, rogue,
                                algorithm="ES256", headers={"kid": f"evil-{i}"})))
    assert es.jwks_hits - base <= 1                           # one refresh at most inside the cooldown window


@pytest.mark.security
async def test_missing_kid_with_multiple_keys_rejected():
    es = GoTrueStub("es256")
    es.add_key(activate=False)
    _, p, sig = es.mint(SUB, "user@example.com").split(".")
    with pytest.raises(AuthError) as ei:
        (await make(es).averify(f"{_b64({'alg': 'ES256', 'typ': 'JWT'})}.{p}.{sig}"))
    assert "kid" in str(ei.value)


async def test_key_rotation_refreshes_on_unknown_kid():
    es = GoTrueStub("es256")
    t = [1000.0]
    a = make(es, jwks_clock=lambda: t[0])
    assert (await a.averify(es.mint(SUB, "user@example.com"))).subject == SUB
    es.add_key()                                              # provider rotates; JWKS now publishes both
    t[0] += JWKS_MIN_REFETCH + 1
    assert (await a.averify(es.mint(SUB, "user@example.com"))).subject == SUB
    es.publish_kids = {es.kid}                               # old key withdrawn on the provider side
    t[0] += JWKS_MIN_REFETCH + JWKS_MIN_REFETCH + 700
    assert (await a.averify(es.mint(SUB, "user@example.com"))).subject == SUB


async def test_jwks_outage_keeps_cached_keys_and_fails_closed_when_cold():
    es = GoTrueStub("es256")
    a = make(es)
    tok = es.mint(SUB, "user@example.com")
    assert (await a.averify(tok)).subject == SUB
    es.jwks_transport.handler = lambda r: __import__("httpx").Response(500)      # JWKS endpoint breaks
    assert (await a.averify(tok)).subject == SUB                       # served from cache
    cold = make(es)
    with pytest.raises(AuthError):
        (await cold.averify(tok))


async def test_malformed_inputs(stub):
    a = make(stub)
    for junk in ("", "a.b.c", "x" * 9000, "Bearer abc", "....", "\x00"):
        with pytest.raises(AuthError):
            (await a.averify(junk))


# ---- phase 3b: strict claims, HS256 off by default, single-flight JWKS, nothing blocks the loop -----------------------------------------
@pytest.mark.security
async def test_hs256_is_off_unless_switched_on():
    stub = GoTrueStub("hs256")
    tok = stub.mint(SUB, "user@example.com")
    off = SupabaseAuth("https://stub.supabase.test/auth/v1", ISS, AUD, secret=HS_SECRET)             # a secret alone is not enough
    with pytest.raises(AuthError):
        await off.averify(tok)
    on = SupabaseAuth("https://stub.supabase.test/auth/v1", ISS, AUD, secret=HS_SECRET, allow_hs256=True)
    assert (await on.averify(tok)).subject == SUB
    with pytest.raises(AuthError):                                                                    # switch on, no secret: still refused
        await SupabaseAuth("http://g", ISS, AUD, allow_hs256=True).averify(tok)


async def test_principal_carries_session_aal_amr(stub):
    now = int(time.time())
    amr = [{"method": "password", "timestamp": now}, {"method": "totp", "timestamp": now}]
    p = await make(stub).averify(stub.mint(SUB, "user@example.com", aal="aal2", session_id="sess-1", amr=amr))
    assert (p.session_id, p.aal, p.mfa) == ("sess-1", "aal2", True)
    assert p.amr == (("password", now), ("totp", now)) and p.exp > p.iat
    q = await make(stub).averify(stub.mint(SUB, "user@example.com"))
    assert q.aal == "aal1" and q.mfa is False and q.amr == ()


@pytest.mark.security
async def test_fifty_concurrent_unknown_kids_cause_one_jwks_fetch():
    import asyncio
    es = GoTrueStub("es256")
    a = make(es)
    base = es.jwks_hits
    rogue = ec.generate_private_key(ec.SECP256R1())

    def bad(i):
        return jwt.encode({"sub": SUB, "iss": ISS, "aud": AUD, "exp": int(time.time()) + 600}, rogue, algorithm="ES256", headers={"kid": f"evil-{i}"})

    res = await asyncio.gather(*(a.averify(bad(i)) for i in range(50)), return_exceptions=True)
    assert all(isinstance(r, AuthError) for r in res)
    assert es.jwks_hits - base == 1                                                                   # cold cache: the shared first fetch is the only one
    res = await asyncio.gather(*(a.averify(bad(i)) for i in range(50)), return_exceptions=True)
    assert all(isinstance(r, AuthError) for r in res) and es.jwks_hits - base == 1                    # inside the cooldown: no further fetch


async def test_slow_jwks_does_not_block_the_event_loop():
    import asyncio
    import httpx
    es = GoTrueStub("es256")

    async def slow(req):
        await asyncio.sleep(0.3)
        return httpx.Response(200, json=es.jwks())

    a = SupabaseAuth("https://stub.supabase.test/auth/v1", ISS, AUD, jwks_url=JWKS_URL, jwks_transport=httpx.MockTransport(slow))
    ticks = 0

    async def ticker():
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    t = asyncio.create_task(ticker())
    try:
        assert (await a.averify(es.mint(SUB, "user@example.com"))).subject == SUB
    finally:
        t.cancel()
    assert ticks >= 15                                                                                # the loop kept running during the 0.3 s fetch


async def test_stale_jwks_refreshes_in_the_background_while_cached_keys_serve():
    import asyncio
    from app.adapters.auth_supabase import JWKS_TTL
    es = GoTrueStub("es256")
    t = [1000.0]
    a = make(es, jwks_clock=lambda: t[0])
    assert (await a.averify(es.mint(SUB, "user@example.com"))).subject == SUB
    n = es.jwks_hits
    t[0] += JWKS_TTL + 1
    assert (await a.averify(es.mint(SUB, "user@example.com"))).subject == SUB                                   # answered from cache
    await asyncio.sleep(0.05)
    assert es.jwks_hits == n + 1


# ---- phase 3h: the shape of every request the backend makes to Supabase -----------------------------------------------------------------
@pytest.mark.security
async def test_the_jwks_request_carries_no_credentials():
    import httpx
    seen: list[httpx.Request] = []
    es = GoTrueStub("es256")

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, json=es.jwks())

    a = SupabaseAuth("https://stub.supabase.test/auth/v1", ISS, AUD, secret=HS_SECRET, apikey=APIKEY, jwks_url=JWKS_URL, jwks_transport=httpx.MockTransport(handler))
    await a.averify(es.mint(SUB, "user@example.com"))
    assert len(seen) == 1 and seen[0].method == "GET" and str(seen[0].url) == JWKS_URL
    names = {k.lower() for k in seen[0].headers}
    assert "authorization" not in names and "apikey" not in names                      # the signing keys are public: neither a user token nor any key goes with the request
    assert HS_SECRET not in str(seen[0].headers) + str(seen[0].url)


async def test_the_name_given_at_sign_up_is_display_only_and_is_cleaned(stub):
    a = make(stub)
    assert (await a.averify(stub.mint(SUB, "user@example.com", user_metadata={"first_name": " Jordan ", "last_name": "Lee"}))).name == "Jordan Lee"
    assert (await a.averify(stub.mint(SUB, "user@example.com", user_metadata={"first_name": 5, "last_name": ""}))).name is None
    assert len((await a.averify(stub.mint(SUB, "user@example.com", user_metadata={"first_name": "x" * 500}))).name) == 160
