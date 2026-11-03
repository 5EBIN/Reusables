"""Typed QueryPlan. The LLM may only produce this; deterministic code compiles and runs it."""
from datetime import date, timedelta
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.plan_vocabulary import DimId, MetricId  # noqa: F401  (re-exported: other modules import them from here)


class Outcome(StrEnum):
    ANSWER = "ANSWER"
    CLARIFY = "CLARIFY"
    CANT_YET = "CANT_YET"
    REFUSE = "REFUSE"


MIN_N = 5
MAX_RANGE_DAYS = 3 * 366


class DateRange(BaseModel):
    start: date
    end: date

    @model_validator(mode="after")
    def _ok(self):
        if self.end < self.start:
            raise ValueError("end before start")
        if self.end - self.start > timedelta(days=MAX_RANGE_DAYS):
            raise ValueError("range too long")
        return self


class Filter(BaseModel):
    dim: DimId
    op: Literal["eq", "neq", "in"]
    value: str | list[str]

    @field_validator("value")
    @classmethod
    def _v(cls, v):
        items = v if isinstance(v, list) else [v]
        if not items or len(items) > 50 or any(len(x) > 200 for x in items):
            raise ValueError("bad filter value")
        return v

    @model_validator(mode="after")
    def _shape(self):
        if self.op == "in" and not isinstance(self.value, list):
            raise ValueError("'in' needs a list")
        if self.op != "in" and isinstance(self.value, list):
            raise ValueError("list only valid with 'in'")
        return self


class TextMatch(BaseModel):
    terms: list[str] = Field(min_length=1, max_length=5)
    mode: Literal["any", "all"] = "any"

    @field_validator("terms")
    @classmethod
    def _t(cls, v):
        if any(not t.strip() or len(t) > 64 for t in v):
            raise ValueError("bad term")
        return v


class QueryPlan(BaseModel):
    outcome: Outcome = Outcome.ANSWER
    metric: MetricId | None = None
    dimensions: list[DimId] = Field(default_factory=list, max_length=2)
    date_range: DateRange | None = None
    filters: list[Filter] = Field(default_factory=list, max_length=10)
    text_match: TextMatch | None = None
    breakdown_question: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    clarify_question: str | None = Field(default=None, max_length=500)
    reason: str | None = Field(default=None, max_length=500)
