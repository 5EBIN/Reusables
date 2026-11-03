"""Embed allow-list: which https sites may frame a survey. Pure validation; the framing header itself is emitted by the web tier from this list.
Rules are strict on purpose: exact origins only (no wildcards, paths, credentials or http), so a typo can never widen who may frame a survey."""
import re
from urllib.parse import urlsplit

MAX_ORIGINS = 10
_HOST = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$|^localhost$")


class EmbedError(ValueError):
    pass


def clean_origin(raw: str) -> str:
    if not isinstance(raw, str) or not raw or len(raw) > 300 or raw != raw.strip():
        raise EmbedError("origin must be a non-empty string")
    if any(ch in raw for ch in " \t\r\n;,'\"<>\\*") or "%" in raw:
        raise EmbedError("origin contains forbidden characters (no wildcards, spaces or separators)")
    try:
        u = urlsplit(raw)
        port = u.port
    except ValueError:
        raise EmbedError("origin is not a valid URL") from None
    if u.scheme != "https":
        raise EmbedError("origin must be https")
    if u.username or u.password or u.path not in ("", "/") or u.query or u.fragment:
        raise EmbedError("origin must be scheme://host[:port] only")
    host = (u.hostname or "").lower()
    if not _HOST.match(host.encode("idna").decode() if host and not host.isascii() else host):
        raise EmbedError("origin host is not valid")
    if host == "localhost":
        raise EmbedError("localhost cannot embed a published survey")
    if port is not None and not 1 <= port <= 65535:
        raise EmbedError("origin port is not valid")
    return f"https://{host}" + (f":{port}" if port not in (None, 443) else "")


def clean_origins(raw: list[str]) -> list[str]:
    if not isinstance(raw, list):
        raise EmbedError("origins must be a list")
    out: list[str] = []
    for x in raw:
        o = clean_origin(x)
        if o not in out:
            out.append(o)
    if len(out) > MAX_ORIGINS:
        raise EmbedError(f"at most {MAX_ORIGINS} origins")
    return out
