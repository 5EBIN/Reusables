"""Report schedule next-run computation (pure) and signed download tokens."""
import base64
import hashlib
import hmac
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


def next_run(freq: str, at: time, tz: str, after: datetime, dow: int | None = None, dom: int | None = None) -> datetime:
    """Next UTC fire time strictly after `after`. dow 0=Mon; dom clamped to 28 to avoid month-end gaps."""
    z = ZoneInfo(tz)
    loc = after.astimezone(z)
    day = loc.date()
    for _ in range(400):
        cand = datetime.combine(day, at, tzinfo=z)
        ok = cand > loc
        if freq == "weekly":
            ok = ok and day.weekday() == (dow if dow is not None else 0)
        elif freq == "monthly":
            ok = ok and day.day == min(dom or 1, 28)
        if ok:
            return cand.astimezone(ZoneInfo("UTC"))
        day += timedelta(days=1)
    raise ValueError("no run found")


def sign(secret: str, org: str, job: str, exp: int) -> str:
    body = f"{org}.{job}.{exp}"
    mac = hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(f"{body}.{base64.urlsafe_b64encode(mac).decode()}".encode()).decode()


def verify(secret: str, token: str, now: int) -> tuple[str, str] | None:
    try:
        org, job, exp, mac = base64.urlsafe_b64decode(token.encode()).decode().split(".")
        good = base64.urlsafe_b64encode(hmac.new(secret.encode(), f"{org}.{job}.{exp}".encode(), hashlib.sha256).digest()).decode()
        if hmac.compare_digest(mac, good) and int(exp) > now:
            return org, job
    except Exception:
        return None
    return None
