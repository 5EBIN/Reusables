"""Pure distribution logic: contact normalisation, CSV mapping, pre-send audience checks, quiet hours, templates."""
import csv
import io
import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
CHANNELS = ("email", "sms", "whatsapp")
ALLOWED_VARS = {"first_name", "name", "link"}
MAX_ROWS = 50_000
FORMULA = ("=", "+", "-", "@", "\t", "\r")


def normalize_email(raw: str | None) -> str | None:
    e = (raw or "").strip().lower()
    return e if EMAIL.match(e) else None


def normalize_phone(raw: str | None, default_cc: str = "971") -> tuple[str | None, bool]:
    """Returns (E.164, changed). UAE-aware: 05x -> +9715x; 00971 -> +971; strips punctuation; Arabic-Indic digits ok."""
    s = (raw or "").translate(AR_DIGITS).strip()
    if not s:
        return None, False
    digits = re.sub(r"[^\d+]", "", s)
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if digits.startswith("+"):
        out = digits
    elif digits.startswith("0"):
        out = f"+{default_cc}{digits[1:]}"
    elif digits.startswith(default_cc):
        out = "+" + digits
    else:
        return None, False
    ok = re.fullmatch(r"\+\d{8,15}", out) is not None
    return (out if ok else None), (out != s)


def mask_phone(p: str | None) -> str | None:
    if not p:
        return None
    return f"{p[:4]} {p[4:6]} ••• {p[-4:]}" if len(p) >= 10 else "•••"


def neutralize(cell: str) -> str:
    """Spreadsheet formula injection guard for any exported cell."""
    return "'" + cell if cell and cell[0] in FORMULA else cell


@dataclass
class ImportReport:
    rows: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    duplicates: int = 0
    columns: list[dict] = field(default_factory=list)
    bom: bool = False


TARGETS = {"name", "email", "phone", "language"}   # everything else must be 'attribute:<key>'


def parse_csv(text: str, mapping: dict[str, str]) -> ImportReport:
    """mapping: csv column -> name|email|phone|language|attribute:<key>. Dedupes by normalised email (else phone)."""
    rep = ImportReport(bom=text.startswith("﻿"))
    text = text.lstrip("﻿")
    rd = csv.DictReader(io.StringIO(text))
    cols = rd.fieldnames or []
    for col, tgt in mapping.items():
        if col not in cols:
            raise ValueError(f"column {col!r} not in file")
        if tgt not in TARGETS and not re.fullmatch(r"attribute:[a-z][a-z0-9_]{0,30}", tgt):
            raise ValueError(f"bad mapping target {tgt!r}")
    seen: set[str] = set()
    status = dict.fromkeys(mapping, "OK")
    for i, raw in enumerate(rd, start=2):
        if i - 1 > MAX_ROWS:
            raise ValueError("too many rows")
        row: dict = {"attributes": {}, "language": "en"}
        for col, tgt in mapping.items():
            v = (raw.get(col) or "").strip()
            if tgt == "email":
                row["email"] = normalize_email(v)
                row["email_raw"] = v
            elif tgt == "phone":
                p, changed = normalize_phone(v)
                row["phone"] = p
                if changed and p:
                    status[col] = "Normalised"
            elif tgt == "language":
                row["language"] = v.lower()[:5] if re.fullmatch(r"[A-Za-z]{2,3}", v) else "en"
            elif tgt == "name":
                row["name"] = v[:200]
            else:
                row["attributes"][tgt.split(":", 1)[1]] = v[:200]
        key = row.get("email") or row.get("phone")
        if not key:
            rep.errors.append({"line": i, "error": "no valid email or phone"})
            continue
        if key in seen:
            rep.duplicates += 1
            continue
        seen.add(key)
        rep.rows.append(row)
    rep.columns = [{"column": c, "maps_to": t, "status": status[c]} for c, t in mapping.items()]
    return rep


@dataclass
class Audience:
    selected: int = 0
    no_consent: int = 0
    suppressed: int = 0
    recently_contacted: int = 0
    will_receive: int = 0
    per_channel: dict = field(default_factory=dict)


def presend_checks(contacts: list[dict], channel_list: list[str], consents: dict, suppressed: set, recent: set) -> tuple[Audience, list[tuple[str, str, str]]]:
    """contacts: {id,email,phone}. consents: {(contact_id,channel): status}. suppressed: {(channel,address)}.
    A contact is counted once; precedence: suppressed > no consent > recently contacted. Returns (audience, [(contact,channel,reason|'ok')])."""
    aud = Audience(selected=len(contacts), per_channel=dict.fromkeys(channel_list, 0))
    plan = []
    for c in contacts:
        reasons = {}
        for ch in channel_list:
            addr = c.get("email") if ch == "email" else c.get("phone")
            if not addr:
                reasons[ch] = "no_address"
            elif (ch, addr) in suppressed:
                reasons[ch] = "suppressed"
            elif consents.get((c["id"], ch), "unknown") != "opt_in":
                reasons[ch] = "no_consent"
            elif c["id"] in recent:
                reasons[ch] = "recent"
            else:
                reasons[ch] = "ok"
        for ch, r in reasons.items():
            plan.append((c["id"], ch, r))
        oks = [ch for ch, r in reasons.items() if r == "ok"]
        if oks:
            aud.will_receive += 1
            for ch in oks:
                aud.per_channel[ch] += 1
        else:
            vals = set(reasons.values())
            if "suppressed" in vals:
                aud.suppressed += 1
            elif "no_consent" in vals:
                aud.no_consent += 1
            elif "recent" in vals:
                aud.recently_contacted += 1
            else:
                aud.no_consent += 1
    return aud, plan


def next_allowed(now: datetime, tz: str, start: time, end: time) -> datetime:
    """Quiet hours (e.g. 21:00-08:00 local): sends are deferred to the end of the window, never dropped."""
    z = ZoneInfo(tz)
    local = now.astimezone(z)
    t = local.time()
    quiet = (t >= start or t < end) if start > end else (start <= t < end)
    if not quiet:
        return now
    target = local.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    if target <= local:
        target += timedelta(days=1)
    return target.astimezone(now.tzinfo or ZoneInfo("UTC"))


VAR = re.compile(r"\{([a-z_]+)\}")


def validate_template(tmpl: str) -> list[str]:
    bad = [v for v in VAR.findall(tmpl) if v not in ALLOWED_VARS]
    if bad:
        raise ValueError(f"unknown variables: {sorted(set(bad))}")
    return VAR.findall(tmpl)


def render_template(tmpl: str, values: dict[str, str]) -> str:
    validate_template(tmpl)
    return VAR.sub(lambda m: values.get(m.group(1), ""), tmpl)
