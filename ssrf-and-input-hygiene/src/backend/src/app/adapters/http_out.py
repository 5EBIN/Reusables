"""Outbound HTTP port: FakeHttp (tests) and HttpxSender (no redirects, short timeout, resolved-IP re-check done by caller)."""
import asyncio
import socket


class FakeHttp:
    def __init__(self):
        self.posts: list[dict] = []
        self.status = 200
        self.dns: dict[str, list[str]] = {}

    async def resolve(self, host: str) -> list[str]:
        return self.dns.get(host, ["93.184.216.34"])

    async def post(self, url: str, body: bytes, headers: dict) -> int:
        self.posts.append({"url": url, "body": body, "headers": headers})
        return self.status


class HttpxSender:                                               # pragma: no cover (network)
    async def resolve(self, host: str) -> list[str]:
        infos = await asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return sorted({i[4][0] for i in infos})

    async def post(self, url: str, body: bytes, headers: dict) -> int:
        import httpx
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as c:
            return (await c.post(url, content=body, headers=headers)).status_code
