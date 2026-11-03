"""The original product's plan vocabulary: six metrics and eight dimensions. PRODUCT-SPECIFIC. Copy this over `src/.../core/plan_vocabulary.py` (a placeholder) to get the
original behaviour, or write your own members; the plan types, the schema builder and the compiler follow whatever is defined here."""
from enum import StrEnum


class MetricId(StrEnum):
    RESPONSE_COUNT = "RESPONSE_COUNT"
    COMPLETION_RATE = "COMPLETION_RATE"
    NPS = "NPS"
    AVG_RATING = "AVG_RATING"
    CHOICE_SHARE = "CHOICE_SHARE"
    THEME_SHARE = "THEME_SHARE"


class DimId(StrEnum):
    SURVEY = "SURVEY"
    QUESTION = "QUESTION"
    DAY = "DAY"
    WEEK = "WEEK"
    MONTH = "MONTH"
    LOCALE = "LOCALE"
    COLLECTOR = "COLLECTOR"
    THEME = "THEME"
