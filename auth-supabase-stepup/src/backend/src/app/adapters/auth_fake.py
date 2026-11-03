"""Deterministic token checks for tests/dev (HS256 JWTs). Sign-in itself happens browser <-> Supabase; tests mint tokens with make_token."""
import time
import uuid

import jwt

from app.core.ports import AuthError, AuthUnavailable, Principal


class FakeAuth:
    def __init__(self, secret: str, issuer: str = "app", audience: str = "app", ttl: int = 900):
        self.secret, self.issuer, self.audience, self.ttl = secret, issuer, audience, ttl
        self.factors: dict[str, int] = {}                # verified authenticator factors per subject; unset = 1 when the token is aal2, else 0
        self.ended: set[str] = set()                     # session ids the provider has ended (signed out, banned): a live check refuses them
        self.down = False                                # the provider cannot be reached: a live check is AuthUnavailable

    def make_token(self, subject: str, email: str | None = None, *, exp_in: int | None = None,
                   mfa: bool = False, verified: bool = True, issuer: str | None = None,
                   audience: str | None = None, secret: str | None = None, session_id: str | None = None, totp_at: int | None = None, iat: int | None = None, recovery_at: int | None = None) -> str:
        now = int(time.time())
        claims = {"sub": subject, "iss": issuer or self.issuer, "aud": audience or self.audience,
                  "iat": iat or now, "exp": now + (self.ttl if exp_in is None else exp_in),
                  "email": email, "email_verified": verified, "aal": "aal2" if mfa else "aal1", "session_id": session_id or str(uuid.uuid4()),
                  "amr": ([{"method": "recovery", "timestamp": recovery_at}] if recovery_at else [{"method": "password", "timestamp": now}]) + ([{"method": "totp", "timestamp": totp_at or now}] if mfa else [])}
        return jwt.encode(claims, secret or self.secret, algorithm="HS256")

    async def alive(self, bearer: str) -> int | None:
        if self.down:
            raise AuthUnavailable("down")
        p = self.verify(bearer)
        if p.session_id in self.ended:
            raise AuthError("session no longer valid")
        return self.factors.get(p.subject, 1 if p.aal == "aal2" else 0)          # verified authenticator factors: a test can set it per subject

    async def aclose(self) -> None:
        return None

    def verify(self, bearer: str) -> Principal:
        try:
            hdr = jwt.get_unverified_header(bearer)
            if hdr.get("alg") != "HS256":
                raise AuthError("bad alg")
            c = jwt.decode(bearer, self.secret, algorithms=["HS256"], audience=self.audience,
                           issuer=self.issuer, options={"require": ["exp", "sub", "iss", "aud"]})
        except jwt.PyJWTError as e:
            raise AuthError(str(e)) from e
        amr = tuple((str(e["method"]), e.get("timestamp")) for e in c.get("amr", []) if isinstance(e, dict) and "method" in e)
        return Principal(c["sub"], c["iss"], c.get("email"), bool(c.get("email_verified")), c.get("aal") == "aal2", c.get("session_id"),
                         "aal2" if c.get("aal") == "aal2" else "aal1", amr, c.get("iat"), c.get("exp"))

    async def averify(self, bearer: str) -> Principal:
        return self.verify(bearer)

    async def ready(self) -> bool:
        return True
