"""Supabase Auth (GoTrue) adapter: strict, non-blocking JWT verification (asymmetric signing keys from the project's JWKS; HS256 only as a legacy fallback that
production refuses) + REST calls.

Authorization never comes from token claims: only (iss, sub) -> users.id, the verified email and the aal/amr/session_id claims are used;
roles and memberships live in our database. Errors are deliberately generic (no account enumeration).
"""
import asyncio
import time
from collections.abc import Callable
from typing import Any

import httpx
import jwt

from app.core.ports import AuthError, AuthUnavailable, Principal

ASYM_ALGS = {"RS256": "RSA", "ES256": "EC"}          # alg -> required JWK kty (blocks HS/RS confusion and kty mismatch)
LEEWAY = 10                                           # seconds of clock skew tolerated on exp/nbf/iat
JWKS_TTL = 600.0                                      # after this the cache is refreshed in the background while the cached keys keep serving
JWKS_MIN_REFETCH = 30.0                               # at most one JWKS fetch per this window, whatever kids attackers send
MAX_TOKEN_LEN = 8192
AUDIENCE = "authenticated"
LIVE_TIMEOUT = 5.0                                    # seconds one live check waits for the provider before the action fails closed
NOT_A_VERDICT = {408, 429}                            # 4xx answers that say "try later", not "this session is gone"


class _Jwks:
    """JWKS cache, async. Cached keys keep serving while a stale cache is refreshed in the background. An unknown kid triggers ONE refetch that every
    concurrent caller shares (single flight), and refetches are at most one per JWKS_MIN_REFETCH, so attacker-supplied kids cannot cause a fetch loop."""

    def __init__(self, url: str, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 5.0, clock: Callable[[], float] = time.monotonic):
        self.url, self.transport, self.timeout, self.clock = url, transport, timeout, clock
        self.keys: dict[str, dict[str, Any]] = {}
        self.fetched: float | None = None
        self.attempted: float | None = None
        self.fetches = 0
        self._inflight: asyncio.Task | None = None
        self._background: set[asyncio.Task] = set()
        self._pyjwk: dict[str, Any] = {}

    def _cooled(self) -> bool:
        return self.attempted is None or self.clock() - self.attempted >= JWKS_MIN_REFETCH

    def _stale(self) -> bool:
        return self.fetched is None or self.clock() - self.fetched > JWKS_TTL

    async def _fetch(self) -> None:
        self.attempted = self.clock()
        self.fetches += 1
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout, follow_redirects=False) as c:
                r = await c.get(self.url, headers={"accept": "application/json"})
            r.raise_for_status()
            keys = {k["kid"]: k for k in r.json().get("keys", []) if isinstance(k, dict) and k.get("kid")}
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
            return                                     # keep serving the previous cache; never raise upstream detail
        if keys:
            self.keys, self.fetched, self._pyjwk = keys, self.clock(), {}

    async def _refresh(self) -> None:
        """One fetch shared by every caller that arrives while it runs. A caller that is cancelled does not cancel the fetch."""
        if self._inflight is None or self._inflight.done():
            self._inflight = asyncio.get_running_loop().create_task(self._fetch())
        await asyncio.shield(self._inflight)

    def _refresh_in_background(self) -> None:
        if (self._inflight is None or self._inflight.done()) and self._cooled():
            t = asyncio.get_running_loop().create_task(self._refresh())
            self._background.add(t)
            t.add_done_callback(self._background.discard)

    async def ready(self) -> bool:
        """Keys in hand (stale ones count: they keep verifying), or one fetch now; a cold cache is retried at most once per JWKS_MIN_REFETCH."""
        if not self.keys and (self._cooled() or (self._inflight is not None and not self._inflight.done())):
            await self._refresh()
        return bool(self.keys)

    async def get(self, kid: str | None) -> Any:
        """The public key (a cryptography key object) for `kid`."""
        if not self.keys:
            if self._cooled() or (self._inflight is not None and not self._inflight.done()):
                await self._refresh()
        elif self._stale():
            self._refresh_in_background()
        if kid is None:
            if len(self.keys) == 1:
                kid = next(iter(self.keys))
            else:
                raise AuthError("kid required")
        elif kid not in self.keys and (self._cooled() or (self._inflight is not None and not self._inflight.done())):
            await self._refresh()                       # key rotation: bounded by the cooldown, shared by concurrent callers
        jwk = self.keys.get(kid)
        if jwk is None:
            raise AuthError("unknown kid")
        return jwk


class SupabaseAuth:
    def __init__(self, base_url: str, issuer: str, audience: str = AUDIENCE, *, secret: str | None = None, allow_hs256: bool = False,
                 jwks_url: str | None = None, apikey: str = "", redirect_to: str | None = None,
                 transport: httpx.AsyncBaseTransport | None = None, jwks_transport: httpx.AsyncBaseTransport | None = None,
                 timeout: float = 10.0, jwks_clock: Callable[[], float] = time.monotonic):
        self.base, self.issuer, self.audience, self.secret = base_url.rstrip("/"), issuer, audience, secret
        self.allow_hs256 = bool(allow_hs256 and secret)  # legacy shared-secret tokens: only with the explicit switch AND a secret
        self.jwks = _Jwks(jwks_url, jwks_transport, clock=jwks_clock) if jwks_url else None
        self._apikey, self.redirect_to, self.transport, self.timeout = apikey, redirect_to, transport, timeout
        self._live: httpx.AsyncClient | None = None      # one client for every live check (connection reuse), made on first use and closed at shutdown

    def __repr__(self) -> str:                          # never print secrets
        return f"SupabaseAuth(base={self.base!r}, issuer={self.issuer!r})"

    async def ready(self) -> bool:
        return await self.jwks.ready() if self.jwks else self.allow_hs256

    # ---- JWT verification (no blocking call: the JWKS is fetched with httpx.AsyncClient) -----------------------
    async def averify(self, bearer: str) -> Principal:
        if not isinstance(bearer, str) or not bearer or len(bearer) > MAX_TOKEN_LEN:
            raise AuthError("malformed")
        try:
            hdr = jwt.get_unverified_header(bearer)
            alg = hdr.get("alg")
            if alg == "HS256" and self.allow_hs256:
                key: Any = self.secret
            elif alg in ASYM_ALGS and self.jwks:
                jwk = await self.jwks.get(hdr.get("kid"))
                if jwk.get("kty") != ASYM_ALGS[alg] or jwk.get("use", "sig") != "sig":
                    raise AuthError("key/alg mismatch")
                kid = jwk["kid"]
                key = self.jwks._pyjwk.get(kid) or self.jwks._pyjwk.setdefault(kid, jwt.PyJWK(jwk).key)
            else:
                raise AuthError("unsupported alg")      # includes none, HS256 unless allowed, RS/ES without JWKS
            c = jwt.decode(bearer, key, algorithms=[alg], audience=self.audience, issuer=self.issuer, leeway=LEEWAY,
                           options={"require": ["exp", "sub", "iss", "aud"]})
        except AuthError:
            raise
        except (jwt.PyJWTError, ValueError, TypeError, KeyError) as e:
            raise AuthError(type(e).__name__) from None
        sub = c["sub"]
        if not isinstance(sub, str) or not sub.strip() or len(sub) > 128:
            raise AuthError("bad sub")
        if c.get("role", "authenticated") != "authenticated" or c.get("is_anonymous") is True:
            raise AuthError("not an end-user session")  # anon / service_role / anonymous sign-ins never act as users
        meta = c.get("user_metadata") if isinstance(c.get("user_metadata"), dict) else {}
        if any(f is False for f in (c.get("email_verified"), c.get("email_confirmed_at"), meta.get("email_verified"))):
            raise AuthError("email not confirmed")
        # GoTrue only mints sessions for confirmed users when "Confirm email" is on; an absent claim is trusted only
        # because docs/SUPABASE_SETTINGS.md requires that setting. An explicit false is always refused above.
        email = c.get("email") if isinstance(c.get("email"), str) else None
        aal = c.get("aal") if c.get("aal") in ("aal1", "aal2") else "aal1"
        session_id = c.get("session_id") if isinstance(c.get("session_id"), str) and c.get("session_id") else None
        amr = tuple((str(e["method"]), int(e["timestamp"]) if isinstance(e.get("timestamp"), (int, float)) else None)
                    for e in (c.get("amr") if isinstance(c.get("amr"), list) else []) if isinstance(e, dict) and isinstance(e.get("method"), str))
        iat = c.get("iat") if isinstance(c.get("iat"), (int, float)) else None
        given = " ".join(v.strip() for v in (meta.get("first_name"), meta.get("last_name")) if isinstance(v, str) and v.strip())[:160] or None
        return Principal(sub, c["iss"], email, True, aal == "aal2", session_id, aal, amr, int(iat) if iat is not None else None, int(c["exp"]), given)

    async def alive(self, bearer: str) -> int | None:
        """The live check for sensitive actions: GET {SUPABASE_URL}/auth/v1/user with the publishable key in `apikey` and the user's own token, never cached. A signed-out,
        revoked, banned or deleted user is refused by the provider even though the token still verifies offline until it expires. Every 4xx except 408 and 429 means the
        session is gone (AuthError; GoTrue answers a deleted user or a missing session with 401, 403 or 404 depending on the version). 408, 429, 5xx, a timeout or a network
        error is AuthUnavailable: the action fails closed, it is never allowed on a guess."""
        if self._live is None:
            self._live = httpx.AsyncClient(transport=self.transport)
        headers = {"Authorization": f"Bearer {bearer}", **({"apikey": self._apikey} if self._apikey else {})}
        try:
            r = await self._live.get(f"{self.base}/user", headers=headers, timeout=LIVE_TIMEOUT)
        except httpx.HTTPError as e:
            raise AuthUnavailable(type(e).__name__) from None
        if r.status_code == 200:
            try:
                body = r.json()
                return sum(1 for f in body["factors"] if f.get("status") == "verified") if isinstance(body, dict) and isinstance(body.get("factors"), list) else None
            except ValueError:
                return None
        if 400 <= r.status_code < 500 and r.status_code not in NOT_A_VERDICT:
            raise AuthError("session no longer valid")
        raise AuthUnavailable(f"http {r.status_code}")

    async def aclose(self) -> None:
        if self._live is not None:
            await self._live.aclose()
            self._live = None
