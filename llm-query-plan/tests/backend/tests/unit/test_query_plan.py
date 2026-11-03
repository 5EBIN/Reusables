import pytest
from pydantic import ValidationError
from app.core.query_plan import DateRange, Filter, MetricId, Outcome, QueryPlan, TextMatch


def test_defaults_and_enum_values():
    p = QueryPlan(metric=MetricId.NPS)
    assert p.outcome is Outcome.ANSWER and p.dimensions == [] and p.date_range is None


@pytest.mark.parametrize("bad", [
    {"start": "2026-02-01", "end": "2026-01-01"},
    {"start": "2020-01-01", "end": "2026-01-01"},
    {"start": "nope", "end": "2026-01-01"},
    {"start": "2026-01-01"}, {}, {"start": 5, "end": 6},
])
def test_date_range_rejections(bad):
    with pytest.raises(ValidationError):
        DateRange(**bad)


@pytest.mark.parametrize("bad", [
    {"dim": "SURVEY", "op": "in", "value": "x"}, {"dim": "SURVEY", "op": "eq", "value": ["x"]},
    {"dim": "NOPE", "op": "eq", "value": "x"}, {"dim": "SURVEY", "op": "like", "value": "x"},
    {"dim": "SURVEY", "op": "eq", "value": "x" * 201}, {"dim": "SURVEY", "op": "in", "value": []},
    {"dim": "SURVEY", "op": "in", "value": ["x"] * 51}, {"dim": "SURVEY", "op": "eq"},
])
def test_filter_rejections(bad):
    with pytest.raises(ValidationError):
        Filter(**bad)


@pytest.mark.parametrize("bad", [
    {"terms": []}, {"terms": ["a"] * 6}, {"terms": ["x" * 65]}, {"terms": [" "]}, {"terms": ["a"], "mode": "xor"}, {},
])
def test_text_match_rejections(bad):
    with pytest.raises(ValidationError):
        TextMatch(**bad)


@pytest.mark.parametrize("bad", [
    {"metric": "NOPE"}, {"outcome": "MAYBE"}, {"dimensions": ["DAY", "WEEK", "MONTH"]}, {"filters": [{}] * 11},
    {"clarify_question": "x" * 501},
])
def test_plan_rejections(bad):
    with pytest.raises(ValidationError):
        QueryPlan(**bad)
