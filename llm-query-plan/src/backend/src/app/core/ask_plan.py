"""What the model may say in "Ask your data", and how it becomes a QueryPlan.
The forced JSON schema is derived from QueryPlan itself (so a new QueryPlan field cannot be forgotten); the one difference is that the model names a period and code
resolves it to dates (core/period.py), and that it sees surveys by opaque ids (`s1`, `s2`) which code maps back."""
import copy
import json
import re
import unicodedata
from datetime import date
from typing import Any

from app.core.period import PERIODS, resolve_period
from app.core.query_plan import DateRange, Outcome, QueryPlan
from app.core.rag import inputs_hash

MODEL_ONLY = {"period", "custom_start", "custom_end"}       # in the schema, not on QueryPlan
CODE_ONLY = {"date_range"}                                  # on QueryPlan, resolved from the period
_DROP = {"title", "default", "description", "minLength", "maxLength", "minItems", "maxItems", "pattern", "format", "minimum", "maximum"}   # checked by QueryPlan afterwards


def _inline(node: Any, defs: dict) -> Any:
    if isinstance(node, dict):
        if "$ref" in node:
            return _inline(copy.deepcopy(defs[node["$ref"].rsplit("/", 1)[1]]), defs)
        return {k: _inline(v, defs) for k, v in node.items() if k != "$defs"}
    if isinstance(node, list):
        return [_inline(v, defs) for v in node]
    return node


def _strict(node: Any) -> Any:
    """Every property required, an optional one nullable, objects closed, no `anyOf` of one type and null, no keywords strict mode does not take."""
    if isinstance(node, list):
        return [_strict(v) for v in node]
    if not isinstance(node, dict):
        return node
    node = {k: v for k, v in node.items() if k not in _DROP}
    options = node.get("anyOf")
    if options:
        real = [o for o in options if o.get("type") != "null"]
        if len(real) == 1:                                                  # Optional[X] -> X that also allows null
            merged = {**_strict(real[0]), **{k: v for k, v in node.items() if k != "anyOf"}}
            t = merged.get("type")
            merged["type"] = (t if isinstance(t, list) else [t]) + ["null"] if t else ["null"]
            if "enum" in merged and None not in merged["enum"]:
                merged["enum"] = merged["enum"] + [None]
            return merged
    if node.get("type") == "object":
        props = node.get("properties", {})
        out = {k: _strict(v) for k, v in props.items()}
        optional = set(props) - set(node.get("required", []))
        for k in optional:                                                  # a field with a default: the model must say it, and may say null
            v = out[k]
            t = v.get("type")
            if t and "null" not in (t if isinstance(t, list) else [t]) and "anyOf" not in v:
                v["type"] = (t if isinstance(t, list) else [t]) + ["null"]
                if "enum" in v and None not in v["enum"]:
                    v["enum"] = v["enum"] + [None]
        return {"type": "object", "properties": out, "required": list(out), "additionalProperties": False}
    return {k: _strict(v) if isinstance(v, (dict, list)) else v for k, v in node.items()}


def plan_schema() -> dict:
    """The response schema for the `plan` task: QueryPlan's own schema, strict, with `date_range` replaced by the period and custom dates."""
    raw = QueryPlan.model_json_schema()
    inlined = _inline(raw, raw.get("$defs", {}))
    props = inlined["properties"]
    for k in CODE_ONLY:
        props.pop(k, None)
    props["filters"]["items"]["properties"]["value"] = {"type": "array", "items": {"type": "string"}}      # the model always lists values; code makes a single one a plain value
    props["period"] = {"type": ["string", "null"], "enum": [*PERIODS, None]}
    props["custom_start"] = {"type": ["string", "null"]}
    props["custom_end"] = {"type": ["string", "null"]}
    schema = _strict(inlined)
    schema["properties"]["outcome"] = {"type": "string", "enum": [o.value for o in Outcome]}          # the one field that is never null
    return schema


def _day(v: Any) -> date:
    if not isinstance(v, str):
        raise ValueError("a date is text")  # noqa: TRY004 - the route catches ValueError
    return date.fromisoformat(v)


def to_query_plan(raw: Any, today: date, surveys: dict[str, str] | None = None) -> QueryPlan:
    """A model answer (or a plan that already has `date_range`, as from an older client or the fake model) as a validated QueryPlan.
    `surveys` maps the opaque ids the model saw to real survey ids. Raises ValueError / ValidationError when it is not a valid plan."""
    if not isinstance(raw, dict):
        raise ValueError("a plan is an object")  # noqa: TRY004 - the route catches ValueError
    d = {k: v for k, v in raw.items() if k not in MODEL_ONLY and v is not None}
    period = raw.get("period")
    if "date_range" not in d and period is not None:
        if period == "custom":
            if raw.get("custom_start") is None or raw.get("custom_end") is None:
                raise ValueError("custom needs both dates")
            d["date_range"] = DateRange(start=_day(raw["custom_start"]), end=_day(raw["custom_end"]))
        else:
            d["date_range"] = resolve_period(period, today)
    ids = {k.lower(): v for k, v in (surveys or {}).items()}
    fixed = []
    for f in d.get("filters") or []:
        if isinstance(f, dict):
            f = dict(f)
            vals = f.get("value")
            if isinstance(vals, list) and f.get("op") != "in":              # the schema always carries a list; eq / neq take one value
                if len(vals) == 1:
                    f["value"] = vals[0]
                elif f.get("op") == "eq":                                   # several values with "eq" can only mean "any of"
                    f["op"] = "in"
            if f.get("dim") == "SURVEY":
                v = f["value"]
                f["value"] = [ids.get(x.lower(), x) if isinstance(x, str) else x for x in v] if isinstance(v, list) else ids.get(str(v).lower(), v)
        fixed.append(f)
    if fixed:
        d["filters"] = fixed
    return QueryPlan.model_validate(d)


def normalise_question(text: str) -> str:
    """The question as the cache sees it: Unicode-normalised, case-folded, one space between words, no trailing question mark or full stop (Latin or Arabic)."""
    return re.sub(r"[?؟.!\s]+$", "", unicodedata.normalize("NFKC", " ".join(text.split())).casefold())


def plan_key(text: str, catalogue: dict, fingerprint: str) -> str:
    """What makes two asks the same: the question, everything the model was shown (today's date included) and the model and prompt that answered."""
    return inputs_hash([normalise_question(text), catalogue, fingerprint])


def plan_for_model(plan_json: Any, surveys: dict[str, str]) -> dict:
    """A stored plan (real dates and survey ids) in the model's terms: opaque survey ids and a custom period. A survey the model was not shown is left out."""
    p = json.loads(plan_json) if isinstance(plan_json, str) else dict(plan_json)
    back = {v: k for k, v in surveys.items()}
    dr = p.pop("date_range", None)
    if dr:
        p |= {"period": "custom", "custom_start": dr["start"], "custom_end": dr["end"]}
    kept = []
    for f in p.get("filters") or []:
        if f.get("dim") == "SURVEY":
            vals = f["value"] if isinstance(f["value"], list) else [f["value"]]
            vals = [back[v] for v in vals if v in back]
            if not vals:
                continue
            f = {**f, "value": vals if f["op"] == "in" else vals[0]}
        kept.append(f)
    p["filters"] = kept
    return p
