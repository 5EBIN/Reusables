"""Rule-based response quality. Deterministic, reversible, no model judgement."""
import re
import statistics
from collections import defaultdict
from datetime import datetime, timedelta

RULE_KEYS = ("speeder", "straightline", "duplicate_device", "gibberish", "attention")
DEFAULTS = {"speeder": {"pct": 35, "treatment": "exclude"}, "straightline": {"min_rows": 8, "treatment": "flag"}, "duplicate_device": {"count": 3, "window_h": 24, "treatment": "exclude"},
            "gibberish": {"treatment": "flag"}, "attention": {"treatment": "exclude"}}


class RuleError(ValueError):
    pass


def validate_rules(raw: dict) -> dict:
    if not isinstance(raw, dict) or set(raw) - set(RULE_KEYS):
        raise RuleError("unknown rule")
    out = {k: dict(v) for k, v in DEFAULTS.items()}
    for k, v in raw.items():
        if not isinstance(v, dict):
            raise RuleError(f"{k}: object expected")
        t = v.get("treatment", out[k]["treatment"])
        if t not in ("exclude", "flag", "off"):
            raise RuleError(f"{k}: treatment must be exclude, flag or off")
        out[k]["treatment"] = t
        for f, lo, hi in (("pct", 5, 90), ("min_rows", 3, 100), ("count", 2, 50), ("window_h", 1, 720)):
            if f in v:
                if f not in out[k]:
                    raise RuleError(f"{k}: unexpected field {f}")
                if not isinstance(v[f], int) or isinstance(v[f], bool) or not lo <= v[f] <= hi:
                    raise RuleError(f"{k}.{f} must be an integer {lo}-{hi}")
                out[k][f] = v[f]
        if k == "attention":
            for f in ("question", "expected"):
                if f in v:
                    if not isinstance(v[f], str) or not 1 <= len(v[f]) <= 64:
                        raise RuleError(f"attention.{f} must be a short string")
                    out[k][f] = v[f]
    return out


def gibberish(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 6:
        return False
    if re.search(r"(.)\1{5,}", t):
        return True
    letters = re.sub(r"[\W\d_]", "", t)
    if len(letters) >= 8 and len(set(letters.lower())) / len(letters) < 0.2:
        return True
    if re.search(r"[bcdfghjklmnpqrstvwxz]{7,}", t, re.IGNORECASE):
        return True
    return " " not in t and len(t) > 40


def evaluate(responses: list[dict], rules: dict) -> dict[str, list[str]]:
    """responses: {id, secs|None, device|None, ratings:[...], texts:[...], attn:value|None, at:datetime}. -> {id: [flags]}"""
    flags: dict[str, list[str]] = defaultdict(list)
    secs = [r["secs"] for r in responses if r.get("secs") is not None]
    med = statistics.median(secs) if len(secs) >= 5 else None
    sp = rules["speeder"]
    for r in responses:
        if sp["treatment"] != "off" and med and r.get("secs") is not None and r["secs"] < med * sp["pct"] / 100:
            flags[r["id"]].append("speeder")
        sl = rules["straightline"]
        rt = r.get("ratings") or []
        if sl["treatment"] != "off" and len(rt) >= sl["min_rows"] and len(set(rt)) == 1:
            flags[r["id"]].append("straightline")
        if rules["gibberish"]["treatment"] != "off" and any(gibberish(t) for t in r.get("texts") or []):
            flags[r["id"]].append("gibberish")
        at = rules["attention"]
        if at["treatment"] != "off" and at.get("question") and r.get("attn") is not None and str(r["attn"]) != at.get("expected"):
            flags[r["id"]].append("attention")
    dd = rules["duplicate_device"]
    if dd["treatment"] != "off":
        by: dict[str, list] = defaultdict(list)
        for r in responses:
            if r.get("device"):
                by[r["device"]].append(r)
        win = timedelta(hours=dd["window_h"])
        for rs in by.values():
            rs.sort(key=lambda x: x["at"])
            for i, r in enumerate(rs):
                inwin = [x for x in rs if abs((x["at"] - r["at"]).total_seconds()) <= win.total_seconds()]
                if len(inwin) >= dd["count"]:
                    flags[r["id"]].append("duplicate_device")
    return {k: sorted(set(v)) for k, v in flags.items()}


def treatment_for(flag: str, rules: dict) -> str:
    return rules[{"speeder": "speeder", "straightline": "straightline", "duplicate_device": "duplicate_device", "gibberish": "gibberish", "attention": "attention"}[flag]]["treatment"]


def should_exclude(flag_list: list[str], rules: dict) -> str | None:
    for f in flag_list:
        if treatment_for(f, rules) == "exclude":
            return f
    return None


_ = datetime  # re-exported for type hints in callers
