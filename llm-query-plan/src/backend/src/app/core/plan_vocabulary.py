"""PLACEHOLDER vocabulary so `query_plan.py` imports. Replace the members with your own metric and dimension ids (the model may only choose from these).
The original product's real vocabulary is in examples/backend/src/app/core/plan_vocabulary.py."""
from enum import StrEnum


class MetricId(StrEnum):
    COUNT = "COUNT"
    AVERAGE = "AVERAGE"


class DimId(StrEnum):
    GROUP = "GROUP"
    DAY = "DAY"
