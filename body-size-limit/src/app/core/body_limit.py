"""A request body size limit for a whole ASGI API.

FastAPI reads and parses a request body BEFORE dependencies (authentication) run, so without a limit any caller, authenticated or not,
can make the server buffer an arbitrarily large JSON body. This pure-ASGI middleware refuses it first: by Content-Length when the client
declares one, and by counting the bytes as they stream in when it does not (chunked bodies).

Default limit: DEFAULT_BODY_BYTES (2 MB). List every route that legitimately carries more in OVERRIDES, and nowhere else.

Over the limit: HTTP 413 with a fixed JSON body, before the route code (and before any authentication) runs.
"""
from __future__ import annotations

import json
import re


MB = 1024 * 1024
DEFAULT_BODY_BYTES = 2 * MB
OVERRIDES: tuple[tuple[re.Pattern, int], ...] = (
    (re.compile(r"^/api/v1/items/[^/]+/upload/?$"), 8 * MB),        # example: one upload route that may carry more
)
_BODYLESS = {"GET", "HEAD", "OPTIONS", "DELETE"}


def limit_for(path: str) -> int:
    for pattern, limit in OVERRIDES:
        if pattern.match(path):
            return limit
    return DEFAULT_BODY_BYTES


class BodyTooLarge(Exception):
    pass


class BodyLimitMiddleware:
    def __init__(self, app, default_limit: int | None = None):
        self.app = app
        self.default_limit = default_limit

    def _limit(self, path: str) -> int:
        lim = limit_for(path)
        return lim if self.default_limit is None or lim != DEFAULT_BODY_BYTES else self.default_limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method", "GET") in _BODYLESS:
            await self.app(scope, receive, send)
            return
        limit = self._limit(scope.get("path", ""))
        declared = None
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = None
                break
        if declared is not None and declared > limit:
            await self._reject(send)
            return

        seen = 0
        started = False

        async def counting_receive():
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    raise BodyTooLarge()
            return message

        async def tracking_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except BodyTooLarge:
            if not started:
                await self._reject(send)

    @staticmethod
    async def _reject(send) -> None:
        body = json.dumps({"detail": "Request body is too large."}).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
