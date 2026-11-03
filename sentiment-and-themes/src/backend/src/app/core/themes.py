"""One definition of a theme proposal. It drives the JSON schema the model must follow, the validation of what comes back, and what the route stores:
a proposal is {key, label: {en, ar}, definition, keywords}. Nothing else describes it, so the schema and the route cannot drift apart again."""
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

RESERVED = {"other", "unclassified"}
KEY = re.compile(r"^[a-z][a-z0-9_]{1,40}$")


class ThemeLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    en: str = Field(min_length=1, max_length=80)
    ar: str | None = Field(default=None, max_length=80)      # the schema marks it required (strict mode), null when the model has no Arabic wording; stored data may omit it


class ThemeProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(description="snake_case id, 2-41 characters: letters, digits, underscore, starting with a letter")
    label: ThemeLabel
    definition: str = Field(max_length=500, description="one sentence saying what belongs in this theme")
    keywords: list[str] = Field(max_length=20, description="2-6 words or short phrases as they appear in the answers")

    @field_validator("key")
    @classmethod
    def _key(cls, v: str) -> str:
        k = re.sub(r"[^a-z0-9]+", "_", v.strip().lower()).strip("_")          # "Parking issues" -> parking_issues: normalising a spelling is safe, guessing a meaning is not
        if not KEY.match(k) or k in RESERVED:
            raise ValueError("bad theme key")
        return k

    @field_validator("keywords")
    @classmethod
    def _kw(cls, v: list[str]) -> list[str]:
        out = [w.strip()[:60] for w in v if isinstance(w, str) and w.strip()]
        if not out:
            raise ValueError("a theme needs at least one keyword")
        return out


class ThemeProposals(BaseModel):
    model_config = ConfigDict(extra="forbid")
    themes: list[ThemeProposal]


def inline_refs(schema: dict) -> dict:
    """The model's JSON schema with every $ref replaced by its definition (providers' strict modes do not all follow references)."""
    defs = schema.get("$defs", {})

    def walk(n: Any) -> Any:
        if isinstance(n, dict):
            if "$ref" in n:
                return walk(defs[n["$ref"].split("/")[-1]])
            return {k: walk(v) for k, v in n.items() if k not in ("$defs", "title", "default")}
        if isinstance(n, list):
            return [walk(x) for x in n]
        return n
    return walk(schema)


def strict(n: Any) -> Any:
    """Strict mode wants every object closed with all its properties required (a field with a default is still listed)."""
    if isinstance(n, dict):
        n = {k: strict(v) for k, v in n.items()}
        if n.get("type") == "object" and "properties" in n:
            n["required"], n["additionalProperties"] = list(n["properties"]), False
    elif isinstance(n, list):
        n = [strict(x) for x in n]
    return n


def json_schema() -> dict:
    return strict(inline_refs(ThemeProposals.model_json_schema()))


def valid_proposals(raw: Any) -> list[dict]:
    """The proposals that pass, normalised. Each is judged alone: one bad theme does not discard the others, and nothing is repaired by guessing."""
    out, seen = [], set()
    for t in raw if isinstance(raw, list) else []:
        try:
            p = ThemeProposal.model_validate(t)
        except ValueError:
            continue
        if p.key not in seen:
            seen.add(p.key)
            out.append(p.model_dump())
    return out
