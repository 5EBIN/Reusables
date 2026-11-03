"""Contract suite for AuthProvider run against fake and mocked supabase adapter."""
import jwt
import pytest
from app.adapters.auth_fake import FakeAuth
from app.adapters.auth_supabase import SupabaseAuth
from app.core.ports import AuthError

SECRET = "k" * 40


def _sb():
    return SupabaseAuth("http://gotrue", "app", "app", secret=SECRET, allow_hs256=True)


def _tok(**kw):
    c = {"sub": "s1", "iss": "app", "aud": "app", "exp": 9999999999, "email": "user@example.com", **kw}
    return jwt.encode(c, SECRET, algorithm="HS256")


@pytest.mark.parametrize("prov", [FakeAuth(SECRET), _sb()])
async def test_contract_verify_rejects_garbage_and_none(prov):
    with pytest.raises(AuthError):
        (await prov.averify("nope"))
    with pytest.raises(AuthError):
        (await prov.averify(jwt.encode({"sub": "u", "iss": "app", "aud": "app", "exp": 9999999999}, None, algorithm="none")))


async def test_supabase_verify_ok_and_wrong_iss():
    assert (await _sb().averify(_tok())).subject == "s1"
    with pytest.raises(AuthError):
        (await _sb().averify(_tok(iss="bad")))
