"""Offline GoTrue (Supabase Auth) stand-in. NOT a real Supabase project: it mimics the documented REST contract
(signup, verify, token?grant_type=password|refresh_token, logout, recover, user) with locally generated keys.
Tokens are signed HS256 (shared secret) or ES256 (EC P-256 key published through a JWKS document).
No network: everything runs through httpx.MockTransport."""
import json
import secrets
import time
import uuid

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import ec

ISS = "https://stub.supabase.test/auth/v1"
AUD = "authenticated"
APIKEY = "stub-anon-key"
HS_SECRET = "s" * 48
OTP = "654321"


class GoTrueStub:
    def __init__(self, mode: str = "hs256", ttl: int = 3600, reuse_interval: int = 0):
        assert mode in ("hs256", "es256")
        self.mode, self.ttl, self.reuse_interval = mode, ttl, reuse_interval
        self.users: dict[str, dict] = {}                # email -> {id, pw, confirmed}
        self.outbox: list[dict] = []                    # emails GoTrue "sent": {to, kind, otp|token_hash}
        self.refresh: dict[str, dict] = {}              # token -> {email, session, used_at, family}
        self.dead_sessions: set[str] = set()
        self.recovery: dict[str, str] = {}              # token_hash -> email
        self.requests: list[httpx.Request] = []
        self.rate_limit_next: int | None = None         # set to N -> next call answers 429 Retry-After: N
        self.down = False
        self.keys: dict[str, ec.EllipticCurvePrivateKey] = {}
        self.kid = ""
        self.jwks_hits = 0
        self.publish_kids: set[str] | None = None       # None -> publish every key
        if mode == "es256":
            self.add_key()
        self.transport = httpx.MockTransport(self._handle)
        self.jwks_transport = httpx.MockTransport(self._jwks)

    # ---- keys / tokens ---------------------------------------------------------------------------------------
    def add_key(self, kid: str | None = None, *, activate: bool = True) -> str:
        kid = kid or f"k-{uuid.uuid4().hex[:8]}"
        self.keys[kid] = ec.generate_private_key(ec.SECP256R1())
        if activate:
            self.kid = kid
        return kid

    def jwks(self) -> dict:
        out = []
        for kid, k in self.keys.items():
            if self.publish_kids is not None and kid not in self.publish_kids:
                continue
            jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(k.public_key()))
            out.append({**jwk, "kid": kid, "alg": "ES256", "use": "sig"})
        return {"keys": out}

    def _jwks(self, req: httpx.Request) -> httpx.Response:
        self.jwks_hits += 1
        return httpx.Response(200, json=self.jwks())

    def mint(self, sub: str, email: str | None, *, exp_in: int | None = None, headers: dict | None = None,
             key=None, alg: str | None = None, **claims) -> str:
        now = int(time.time())
        body = {"sub": sub, "iss": ISS, "aud": AUD, "iat": now, "exp": now + (self.ttl if exp_in is None else exp_in),
                "email": email, "role": "authenticated", "aal": "aal1", "session_id": str(uuid.uuid4()),
                "app_metadata": {"provider": "email"}, "user_metadata": {}, **claims}
        body = {k: v for k, v in body.items() if v is not None or k == "email"}
        if sub is ...:
            body.pop("sub")
        for k in [k for k, v in claims.items() if v is ...]:
            body.pop(k, None)                           # claims={'sub': ...} drops the claim entirely
        if self.mode == "hs256":
            return jwt.encode(body, key or HS_SECRET, algorithm=alg or "HS256", headers=headers)
        return jwt.encode(body, key or self.keys[self.kid], algorithm=alg or "ES256", headers={"kid": self.kid, **(headers or {})})

    def _session(self, email: str, session: str, family: str) -> dict:
        u = self.users[email]
        rt = secrets.token_urlsafe(9)
        self.refresh[rt] = {"email": email, "session": session, "used_at": None, "family": family}
        at = self.mint(u["id"], email, session_id=session, user_metadata={"email_verified": True})
        return {"access_token": at, "refresh_token": rt, "token_type": "bearer", "expires_in": self.ttl,
                "user": {"id": u["id"], "email": email}}

    # ---- REST ------------------------------------------------------------------------------------------------
    def _err(self, status: int, code: str) -> httpx.Response:
        return httpx.Response(status, json={"code": status, "error_code": code, "msg": code})

    def _bearer_session(self, req: httpx.Request) -> tuple[str, str] | None:
        h = req.headers.get("authorization", "")
        if not h.lower().startswith("bearer ") or h[7:] == APIKEY:
            return None
        try:
            c = jwt.decode(h[7:], HS_SECRET if self.mode == "hs256" else self.keys[self.kid].public_key(),
                           algorithms=["HS256" if self.mode == "hs256" else "ES256"], audience=AUD)
        except jwt.PyJWTError:
            return None
        if c["session_id"] in self.dead_sessions:
            return None
        return c["email"], c["session_id"]

    def _handle(self, req: httpx.Request) -> httpx.Response:
        self.requests.append(req)
        if self.down:
            raise httpx.ConnectError("stub down", request=req)
        if self.rate_limit_next is not None:
            n, self.rate_limit_next = self.rate_limit_next, None
            return httpx.Response(429, headers={"retry-after": str(n)}, json={"error_code": "over_request_rate_limit"})
        if req.headers.get("apikey") != APIKEY:
            return self._err(401, "no_authorization")
        path = req.url.path.removeprefix("/auth/v1")
        body = json.loads(req.content) if req.content else {}
        q = dict(req.url.params)
        email = (body.get("email") or "").lower()
        if path == "/signup" and req.method == "POST":
            if email not in self.users:
                self.users[email] = {"id": str(uuid.uuid4()), "pw": body["password"], "confirmed": False}
                self.outbox.append({"to": email, "kind": "signup", "otp": OTP})
            return httpx.Response(200, json={"id": self.users[email]["id"], "email": email})          # obfuscated for existing users
        if path == "/verify" and req.method == "POST":
            if body.get("type") == "recovery":
                em = self.recovery.pop(body.get("token_hash", ""), None)
                if not em:
                    return self._err(403, "otp_expired")
                return httpx.Response(200, json=self._session(em, str(uuid.uuid4()), secrets.token_hex(4)))
            u = self.users.get(email)
            if not u or body.get("token") != OTP or body.get("type") not in ("signup", "email"):
                return self._err(403, "otp_expired")
            if body["type"] == "signup" and u["confirmed"]:
                return self._err(403, "otp_expired")
            u["confirmed"] = True
            return httpx.Response(200, json=self._session(email, str(uuid.uuid4()), secrets.token_hex(4)))
        if path == "/token" and req.method == "POST":
            if q.get("grant_type") == "password":
                u = self.users.get(email)
                if not u or u["pw"] != body.get("password"):
                    return self._err(400, "invalid_credentials")
                if not u["confirmed"]:
                    return self._err(400, "email_not_confirmed")
                return httpx.Response(200, json=self._session(email, str(uuid.uuid4()), secrets.token_hex(4)))
            if q.get("grant_type") == "refresh_token":
                rec = self.refresh.get(body.get("refresh_token", ""))
                if not rec or rec["session"] in self.dead_sessions:
                    return self._err(400, "refresh_token_not_found")
                if rec["used_at"] is not None and time.time() - rec["used_at"] >= self.reuse_interval:     # >=: with no reuse window a replay is always refused, even when a coarse clock (Windows ~15 ms) reads 0.0 elapsed
                    self.dead_sessions.add(rec["session"])           # reuse detection: revoke the whole family
                    return self._err(400, "refresh_token_already_used")
                rec["used_at"] = time.time()
                return httpx.Response(200, json=self._session(rec["email"], rec["session"], rec["family"]))
            return self._err(400, "unsupported_grant_type")
        if path == "/logout" and req.method == "POST":
            who = self._bearer_session(req)
            if not who:
                return self._err(401, "bad_jwt")
            em, sid = who
            scope = q.get("scope", "global")
            for rec in self.refresh.values():
                if rec["email"] == em and (scope == "global" or (scope == "local" and rec["session"] == sid)
                                           or (scope == "others" and rec["session"] != sid)):
                    self.dead_sessions.add(rec["session"])
            return httpx.Response(204)
        if path == "/recover" and req.method == "POST":
            if email in self.users:
                th = secrets.token_hex(16)
                self.recovery[th] = email
                self.outbox.append({"to": email, "kind": "recovery", "token_hash": th})
            return httpx.Response(200, json={})              # identical for unknown emails
        if path == "/user" and req.method == "PUT":
            who = self._bearer_session(req)
            if not who:
                return self._err(401, "bad_jwt")
            self.users[who[0]]["pw"] = body["password"]
            return httpx.Response(200, json={"email": who[0]})
        return self._err(404, "not_found")

    # ---- helpers for tests ------------------------------------------------------------------------------------
    def last_mail(self, to: str, kind: str) -> dict:
        return next(m for m in reversed(self.outbox) if m["to"] == to.lower() and m["kind"] == kind)

    def env(self) -> dict:
        e = {"AUTH_PROVIDER": "supabase", "SUPABASE_URL": "https://stub.supabase.test", "SUPABASE_PUBLISHABLE_KEY": APIKEY,
             "RATE_LIMIT": "1000", "STORE_ROOT": "/tmp/app-test-store"}
        if self.mode == "hs256":
            e["AUTH_ALLOW_HS256"] = "true"
            e["SUPABASE_JWT_SECRET"] = HS_SECRET
        return e
