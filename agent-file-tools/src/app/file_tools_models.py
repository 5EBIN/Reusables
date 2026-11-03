"""Request models for the three tools. Numbers are clamped, never trusted; a bad value falls back to its default."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

class _Clamp(BaseModel):
    model_config = ConfigDict(extra="ignore")


def _clamp_int(lo: int, hi: int, default=None):
    def fix(v):
        if v is None or isinstance(v, bool):
            return default
        try:
            return max(lo, min(hi, int(v)))
        except (TypeError, ValueError):
            return default
    return fix
class GlobReq(_Clamp):
    pattern: str = Field(min_length=1, max_length=300)
    limit: int | None = None

    @field_validator("limit", mode="before")
    @classmethod
    def _l(cls, v):
        return _clamp_int(1, 500, None)(v)


class GrepReq(_Clamp):
    pattern: str = Field(min_length=1)
    glob: str | None = Field(default=None, max_length=300)
    type: str | None = Field(default=None, max_length=20)
    mode: str = "content"
    ignore_case: bool = False
    context: int | None = 0
    offset: int | None = 0

    @field_validator("context", mode="before")
    @classmethod
    def _c(cls, v):
        return _clamp_int(0, 5, 0)(v)

    @field_validator("offset", mode="before")
    @classmethod
    def _o(cls, v):
        return _clamp_int(0, 10 ** 6, 0)(v)


class ReadReq(_Clamp):
    path: str | None = Field(default=None, max_length=500)
    ref: str | None = Field(default=None, max_length=10)
    offset: int | None = None
    limit: int | None = None

    @field_validator("offset", mode="before")
    @classmethod
    def _o(cls, v):
        return _clamp_int(0, 10 ** 6, None)(v)

    @field_validator("limit", mode="before")
    @classmethod
    def _l(cls, v):
        return _clamp_int(1, 1000, None)(v)
