"""Static registry: metric -> SQL fragments, dimension -> column expression. Never built from user/LLM text."""
from dataclasses import dataclass

from app.core.query_plan import DimId, MetricId

TZ = "Asia/Dubai"


@dataclass(frozen=True)
class Metric:
    label: str
    needs_answers: bool
    requires: tuple[DimId, ...]
    min_n: bool
    # selected aggregate columns (constants)
    select: str


METRICS: dict[MetricId, Metric] = {
    MetricId.RESPONSE_COUNT: Metric("Responses", False, (), False, "count(*) as n"),
    MetricId.COMPLETION_RATE: Metric("Completion rate", False, (), True,
        "count(*) as n, count(*) filter (where r.completed_at is not null) as completed"),
    MetricId.NPS: Metric("NPS", True, (DimId.SURVEY, DimId.QUESTION), True,
        "count(*) as n, count(*) filter (where a.value_num >= 9) as promoters, "
        "count(*) filter (where a.value_num <= 6) as detractors"),
    MetricId.AVG_RATING: Metric("Average rating", True, (DimId.SURVEY, DimId.QUESTION), True,
        "count(*) as n, avg(a.value_num) as avg"),
    MetricId.CHOICE_SHARE: Metric("Choice share", True, (DimId.SURVEY, DimId.QUESTION), True,
        "count(*) as n"),
    MetricId.THEME_SHARE: Metric("Theme share", False, (DimId.SURVEY, DimId.QUESTION), True,
        "count(*) as n"),
}

# dimension -> (select expression, kind)  kind: uuid|text|time
DIMS: dict[DimId, tuple[str, str]] = {
    DimId.SURVEY: ("r.survey_id", "uuid"),
    DimId.QUESTION: ("a.question_id", "text"),
    DimId.DAY: (f"date_trunc('day', r.received_at at time zone '{TZ}')::date", "time"),
    DimId.WEEK: (f"date_trunc('week', r.received_at at time zone '{TZ}')::date", "time"),
    DimId.MONTH: (f"date_trunc('month', r.received_at at time zone '{TZ}')::date", "time"),
    DimId.LOCALE: ("r.locale", "text"),
    DimId.COLLECTOR: ("r.collector_id", "uuid"),
    DimId.THEME: ("t.theme", "text"),
}
LABELS = {m.value: v.label for m, v in METRICS.items()}
