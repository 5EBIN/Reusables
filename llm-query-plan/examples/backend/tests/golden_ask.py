"""The golden questions for "Ask your data": what the model should understand, compared by MEANING (metric, dates, grouping, filters, search words), never by the model's wording.
Used offline (the expectations are themselves valid plans and cover every metric and period) and live (tests/integration/test_live_golden.py: the real model must match most of them).
The catalogue is fixed (two surveys with fixed ids) and so is "today", so every expected date is exact."""
import json
import uuid
from datetime import date
from types import SimpleNamespace as NS

from app.app.analytics.catalogue import ask_catalogue, tidy_plan
from app.core.ask_plan import to_query_plan
from app.core.period import resolve_period
from app.core.query_plan import DimId, MetricId

TODAY = date(2026, 10, 24)
TZ = "Asia/Dubai"
RESIDENT, VISITOR = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000001"), uuid.UUID("bbbbbbbb-0000-4000-8000-000000000002")
ROWS = [NS(id=RESIDENT, title=json.dumps({"default": "Resident survey"}), defn=json.dumps({"pages": [{"elements": [
            {"type": "rating", "name": "nps", "title": "How likely are you to recommend us?"}, {"type": "rating", "name": "overall", "title": "Overall satisfaction"},
            {"type": "radiogroup", "name": "kind", "title": "Unit type"}, {"type": "comment", "name": "comments", "title": "Anything else?"}]}]})),
        NS(id=VISITOR, title=json.dumps({"default": "Visitor feedback"}), defn=json.dumps({"pages": [{"elements": [{"type": "rating", "name": "csat", "title": "How was the visit?"}]}]}))]
TAG = {str(RESIDENT): "resident", str(VISITOR): "visitor"}


def case(q, metric=None, period=None, dims=(), filters=None, terms=None, outcome="ANSWER", dates=None):
    """`period` is a named period (resolved with TODAY) or `dates`=(start, end); `filters` maps a dimension to the one value expected (surveys by tag)."""
    return {"q": q, "outcome": outcome, "metric": metric, "period": period, "dates": dates, "dims": list(dims), "filters": filters or {}, "terms": terms}


R, V = {"SURVEY": "resident"}, {"SURVEY": "visitor"}
CASES = [
    case("How many responses did we get last month?", "RESPONSE_COUNT", "last_month"),
    case("كم عدد الردود في الشهر الماضي؟", "RESPONSE_COUNT", "last_month"),
    case("How many people responded this year?", "RESPONSE_COUNT", "this_year"),
    case("What is our NPS this quarter?", "NPS", "this_quarter", filters=R | {"QUESTION": "nps"}),
    case("ما هو صافي نقاط الترويج هذه السنة؟", "NPS", "this_year", filters=R | {"QUESTION": "nps"}),
    case("NPS by month over the last quarter", "NPS", "last_quarter", ["MONTH"], R | {"QUESTION": "nps"}),
    case("Average overall satisfaction by language this year", "AVG_RATING", "this_year", ["LOCALE"], R | {"QUESTION": "overall"}),
    case("متوسط الرضا العام حسب اللغة هذه السنة", "AVG_RATING", "this_year", ["LOCALE"], R | {"QUESTION": "overall"}),
    case("كم شخصاً أجاب هذه السنة؟", "RESPONSE_COUNT", "this_year"),
    case("عدد الردود الأسبوعي في آخر 30 يوما", "RESPONSE_COUNT", "last_30_days", ["WEEK"]),
    case("Completion rate in the last 7 days", "COMPLETION_RATE", "last_7_days"),
    case("Completion rate by language this quarter", "COMPLETION_RATE", "this_quarter", ["LOCALE"]),
    case("كم نسبة إكمال الاستبيان في آخر 30 يوما؟", "COMPLETION_RATE", "last_30_days"),
    case("Responses per week in the last 30 days", "RESPONSE_COUNT", "last_30_days", ["WEEK"]),
    case("Daily responses this month", "RESPONSE_COUNT", "this_month", ["DAY"]),
    case("Responses between 1 March and 15 April 2026", "RESPONSE_COUNT", dates=("2026-03-01", "2026-04-15")),
    case("كم رداً بين 1 مارس و 15 أبريل 2026؟", "RESPONSE_COUNT", dates=("2026-03-01", "2026-04-15")),
    case("Responses yesterday", "RESPONSE_COUNT", dates=("2026-10-23", "2026-10-23")),
    case("How many responses did we get in 2025?", "RESPONSE_COUNT", dates=("2025-01-01", "2025-12-31")),
    case("Arabic responses this month", "RESPONSE_COUNT", "this_month", filters={"LOCALE": "ar"}),
    case("English responses last quarter", "RESPONSE_COUNT", "last_quarter", filters={"LOCALE": "en"}),
    case("How many answers mention parking last month?", "RESPONSE_COUNT", "last_month", terms=["parking"]),
    case("كم إجابة تذكر المصعد الشهر الماضي؟", "RESPONSE_COUNT", "last_month", terms=["المصعد"]),
    case("Share of each unit type this year", "CHOICE_SHARE", "this_year", filters=R | {"QUESTION": "kind"}),
    case("How were visits rated by visitors in the last 30 days?", "AVG_RATING", "last_30_days", filters=V | {"QUESTION": "csat"}),
    case("ما هو متوسط تقييم الزوار هذا الشهر؟", "AVG_RATING", "this_month", filters=V | {"QUESTION": "csat"}),
    case("Visitor feedback rating by week last month", "AVG_RATING", "last_month", ["WEEK"], V | {"QUESTION": "csat"}),
    case("Theme share of the comments this quarter", "THEME_SHARE", "this_quarter", filters=R | {"QUESTION": "comments"}),
    case("NPS", "NPS", None, filters=R | {"QUESTION": "nps"}),                                  # no period named: no dates, the compiler asks which range
    case("Show me john's answers", outcome="REFUSE"),
    case("What is the weather in Dubai?", outcome="REFUSE"),
    case("Compare it with before", outcome="CLARIFY"),
]


def expected_range(c):
    if c["dates"]:
        return c["dates"]
    if c["period"]:
        r = resolve_period(c["period"], TODAY)
        return (str(r.start), str(r.end))
    return None


def catalogue():
    return ask_catalogue(ROWS, None, TODAY, TZ)


def meaning(raw) -> dict:
    """A model answer as the facts the golden case states: after the same resolution and tidying the route applies."""
    cat, ids = catalogue()
    p = tidy_plan(to_query_plan(raw, TODAY, ids), set(ids.values()))
    filters = {f.dim.value: (TAG.get(f.value, f.value) if isinstance(f.value, str) else sorted(f.value)) for f in p.filters}
    return {"outcome": p.outcome.value, "metric": p.metric.value if p.metric else None, "range": (str(p.date_range.start), str(p.date_range.end)) if p.date_range else None,
            "dims": [d.value for d in p.dimensions], "filters": filters, "terms": sorted(t.casefold() for t in p.text_match.terms) if p.text_match else None}


def matches(c, m) -> bool:
    """The case's facts against the model's: a non-answer needs only the outcome; an answer needs the metric, the dates, the grouping and the filters; search words need to include the expected ones."""
    if c["outcome"] != "ANSWER":
        return m["outcome"] == c["outcome"]
    terms_ok = c["terms"] is None and m["terms"] is None or c["terms"] is not None and m["terms"] is not None and {t.casefold() for t in c["terms"]} <= set(m["terms"])
    return (m["outcome"] == "ANSWER" and m["metric"] == c["metric"] and m["range"] == expected_range(c) and m["dims"] == c["dims"] and m["filters"] == c["filters"] and terms_ok)


assert MetricId and DimId             # the vocabularies the cases are written against
