"""Outbound URL guard (SSRF) + webhook signatures. Pure; DNS resolution is injected so tests never hit the network."""
import hashlib
import hmac
import ipaddress
import re
from urllib.parse import urlsplit

HOST_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


class UrlError(ValueError):
    pass


def is_public_ip(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    a = a.ipv4_mapped if getattr(a, "ipv4_mapped", None) else a
    return a.is_global and not (a.is_multicast or a.is_reserved or a.is_loopback or a.is_link_local or a.is_private or a.is_unspecified)


def check_syntax(url: str) -> str:
    if len(url) > 2000 or any(ord(ch) < 33 or ord(ch) > 126 for ch in url):
        raise UrlError("invalid url")
    p = urlsplit(url)
    if p.scheme != "https":
        raise UrlError("https required")
    if p.username or p.password or "@" in p.netloc:
        raise UrlError("credentials in url not allowed")
    if p.fragment:
        raise UrlError("fragment not allowed")
    host = (p.hostname or "").lower()
    try:
        port = p.port
    except ValueError:
        raise UrlError("bad port") from None
    if port not in (None, 443):
        raise UrlError("only port 443 allowed")
    try:
        ipaddress.ip_address(host)
        raise UrlError("ip literals not allowed")
    except ValueError as e:
        if "ip literals" in str(e):
            raise
    if not HOST_RE.match(host) or host.endswith((".local", ".internal", ".localhost", ".lan")) or host == "localhost":
        raise UrlError("host not allowed")
    return host


async def check_url(url: str, resolve) -> str:
    """resolve(host) -> list[str] of IPs. Every address must be public (re-run at send time: DNS rebinding)."""
    host = check_syntax(url)
    ips = await resolve(host)
    if not ips or not all(is_public_ip(i) for i in ips):
        raise UrlError("host resolves to a non-public address")
    return host


def sign(secret: str, ts: int, body: bytes) -> str:
    return "v1=" + hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()


def verify_sig(secret: str, ts: int, body: bytes, sig: str, now: int, tolerance: int = 300) -> bool:
    return abs(now - ts) <= tolerance and hmac.compare_digest(sign(secret, ts, body), sig)
