"""Verified narratives: the model drafts sentences with {{ref:id}} placeholders and claim tokens; code verifies,
renders direction/comparison words from computed values, and substitutes numbers. Labels are data ({{label:key}})."""
import html
import re
from dataclasses import dataclass

from app.core.verifier import REF, Claim, Sentence, render_claim, verify

LABEL = re.compile(r"\{\{label:([a-z0-9_.]+)\}\}")


class NarrativeError(ValueError):
    pass


def fmt(v: float) -> str:
    if float(v).is_integer():
        return f"{int(v):,}"
    return f"{v:,.1f}"


@dataclass
class Rendered:
    text: str
    refs_total: int
    refs_traced: int
    claims: int


def parse_sentences(raw: list[dict]) -> list[Sentence]:
    out = []
    if not isinstance(raw, list) or len(raw) > 20:
        raise NarrativeError("bad draft")
    for r in raw:
        if not isinstance(r, dict) or set(r) - {"template", "claims"} or not isinstance(r.get("template"), str):
            raise NarrativeError("bad sentence")
        claims = []
        for c in r.get("claims", []):
            if not isinstance(c, dict) or set(c) - {"metric_ref", "direction", "comparison_ref"} or c.get("direction") not in ("up", "down", "flat"):
                raise NarrativeError("bad claim")
            claims.append(Claim(c["metric_ref"], c["direction"], c.get("comparison_ref")))
        out.append(Sentence(r["template"], [], claims))
    return out


def render(sentences: list[Sentence], computed: dict[str, float], labels: dict[str, str] | None = None) -> Rendered:
    """Raises NarrativeError on any verification failure. Never partially renders."""
    labels = labels or {}
    parts, total, claims_n = [], 0, 0
    for s in sentences:
        tmpl = LABEL.sub(" ", s.template)           # labels are data: verify the template without them
        ok, why = verify(tmpl, computed)
        if not ok:
            raise NarrativeError(why)
        if any(k not in labels for k in LABEL.findall(s.template)):
            raise NarrativeError("unknown label")
        text = LABEL.sub(lambda m: html.escape(labels[m.group(1)]), s.template)
        for c in s.claims:
            try:
                text += " " + render_claim(c, computed)
            except ValueError as e:
                raise NarrativeError(str(e)) from None
            claims_n += 1
        total += len(REF.findall(text))
        parts.append(text)
    joined = " ".join(parts)
    traced = 0

    def sub(m):
        nonlocal traced
        traced += 1
        return fmt(computed[m.group(1)])
    final = REF.sub(sub, joined)
    return Rendered(final, total, traced, claims_n)
