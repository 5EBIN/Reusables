import pytest
import jwt
from app.adapters.auth_fake import FakeAuth
from app.core.ports import AuthError

A = FakeAuth("s" * 40)


async def test_valid():
    p = (await A.averify(A.make_token("u1", "user@example.com")))
    assert p.subject == "u1" and p.email == "user@example.com" and not p.mfa

async def test_mfa_claim():
    assert (await A.averify(A.make_token("u1", mfa=True))).mfa

@pytest.mark.parametrize("tok", [
    A.make_token("u", exp_in=-10),
    A.make_token("u", issuer="evil"),
    A.make_token("u", audience="other"),
    A.make_token("u", secret="x" * 40),
    jwt.encode({"sub": "u", "iss": "app", "aud": "app", "exp": 9999999999}, None, algorithm="none"),
    "garbage", "", "a.b.c",
])
async def test_rejects(tok):
    with pytest.raises(AuthError):
        (await A.averify(tok))
