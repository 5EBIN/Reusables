"""What "Ask your data" tells the model about the organisation: governed metrics and dimensions, today's date, and the surveys and questions it may name.
Surveys are shown by opaque ids (`s1`, `s2`, ...) that the route maps back; no respondent data, no database ids."""
import json
from datetime import date
from typing import Any

from app.app.analytics.compiler import GROUPABLE
from app.app.analytics.semantic import METRICS
from app.core.period import PERIODS
from app.core.query_plan import DimId, Filter, MetricId, Outcome, QueryPlan
from app.core.redact import redact
from app.db.repos.surveys import SurveyWithDefinition

MAX_SURVEYS = 20
MAX_QUESTIONS = 12
MAX_TITLE = 80
ASKABLE = {"rating", "radiogroup", "dropdown", "checkbox", "tagbox", "boolean", "text", "comment", "ranking"}     # question types that carry an answer
FILTER_DIMS = [DimId.SURVEY, DimId.QUESTION, DimId.LOCALE, DimId.COLLECTOR]


def survey_title(title: Any) -> str:
    t = json.loads(title) if isinstance(title, str) else (title or {})
    return t.get("default") or next(iter(t.values()), "Untitled")


def question_title(e: dict) -> str:
    t = e.get("title")
    return t if isinstance(t, str) else (t or {}).get("default", e["name"])


def survey_questions(defn: Any) -> list[dict]:
    """The named questions of a survey definition (JSON text or decoded), in order."""
    d = json.loads(defn) if isinstance(defn, str) else (defn or {"pages": []})
    return [{"id": e["name"], "title": question_title(e), "type": e.get("type")} for p in d.get("pages", []) for e in p.get("elements", []) if e.get("name")]


def tidy_plan(plan: QueryPlan, all_surveys: set[str]) -> QueryPlan:
    """Fixed rules that remove what a model tends to add and the compiler cannot use, so equal questions give equal plans:
    identical filters are kept once; a SURVEY filter naming every survey is "no filter" (unless the metric needs a survey); a QUESTION filter on a metric that reads no
    answers, or a list of questions beside a text search, is dropped. Nothing is added or changed."""
    needs = METRICS[plan.metric].requires if plan.metric else ()
    reads_answers = plan.metric is not None and (METRICS[plan.metric].needs_answers or plan.metric is MetricId.THEME_SHARE)
    kept: list[Filter] = []
    for f in plan.filters:
        vals = set(f.value if isinstance(f.value, list) else [f.value])
        if f in kept:
            continue
        if f.dim is DimId.SURVEY and DimId.SURVEY not in needs and f.op == "in" and len(all_surveys) > 1 and vals >= all_surveys:
            continue
        if f.dim is DimId.QUESTION and plan.metric is not None and (not reads_answers and (plan.text_match is None or f.op != "eq")):
            continue
        kept.append(f)
    return plan.model_copy(update={"filters": kept}) if kept != plan.filters else plan


def _short(s: str) -> str:
    return redact(s)[:MAX_TITLE]


def ask_catalogue(rows: list[SurveyWithDefinition], selected: Any, today: date, tz: str) -> tuple[dict, dict[str, str]]:
    """(the catalogue for the model, opaque survey id -> real survey id). `rows` is newest first; the surveys are capped, but the one selected on the screen is always in."""
    chosen = sorted(rows[:MAX_SURVEYS], key=lambda r: r.id != selected) if selected is not None else rows[:MAX_SURVEYS]
    if selected is not None and not any(r.id == selected for r in chosen):
        chosen = [r for r in rows if r.id == selected] + chosen[:MAX_SURVEYS - 1]
    surveys, ids = [], {}
    for i, r in enumerate(chosen, 1):
        ids[f"s{i}"] = str(r.id)
        qs = [{"id": q["id"], "title": _short(q["title"]), "type": q["type"]} for q in survey_questions(r.defn) if q["type"] in ASKABLE][:MAX_QUESTIONS]
        surveys.append({"id": f"s{i}", "title": _short(survey_title(r.title)), "questions": qs})
    cat: dict[str, Any] = {
        "today": today.isoformat(), "time_zone": tz,
        "metrics": [{"id": m.value, "label": v.label, "needs": [d.value for d in v.requires]} for m, v in METRICS.items()],
        "dimensions": sorted(d.value for d in GROUPABLE), "filters": [d.value for d in FILTER_DIMS],
        "outcomes": [o.value for o in Outcome], "periods": list(PERIODS), "surveys": surveys,
    }
    if selected is not None:
        cat["selected_survey"] = next(k for k, v in ids.items() if v == str(selected))
    return cat, ids
