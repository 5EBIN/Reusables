"""The forced plan schema for "Ask your data" and the step from a model answer to a QueryPlan. Realistic model outputs (English and Arabic) must conform to the schema
and compile to the expected plan; the clock is fixed, so relative dates are exact."""
import json
import re
import uuid
from datetime import date
from types import SimpleNamespace as NS

import pytest

import app.adapters.llm_task_definitions  # noqa: F401  (registers the example tasks)
from app.adapters.llm_tasks import OUTPUTS, SCHEMAS, strict_compatible, validate_output
from app.app.analytics.catalogue import ask_catalogue, tidy_plan
from app.core.ask_plan import CODE_ONLY, MODEL_ONLY, normalise_question, plan_for_model, plan_key, plan_schema, to_query_plan
from app.core.query_plan import DimId, MetricId, Outcome, QueryPlan

TODAY = date(2026, 10, 24)
SID = uuid.UUID("11111111-2222-3333-4444-555555555555")
SURVEYS = {"s1": str(SID), "s2": str(uuid.uuid4())}


def conforms(schema, v, path="$"):
    """The strict-mode rules we rely on: closed objects with every property present, enums, null only where the type allows it, arrays of the item type."""
    t = schema.get("type")
    types = t if isinstance(t, list) else [t] if t else []
    if v is None:
        assert "null" in types, f"{path}: null not allowed"
        return
    if "enum" in schema:
        assert v in schema["enum"], f"{path}: {v!r} not in enum"
    if "object" in types:
        assert isinstance(v, dict), path
        assert set(v) == set(schema["properties"]), f"{path}: keys {sorted(v)} != {sorted(schema['properties'])}"
        for k, s in schema["properties"].items():
            conforms(s, v[k], f"{path}.{k}")
    elif "array" in types:
        assert isinstance(v, list), path
        for i, x in enumerate(v):
            conforms(schema["items"], x, f"{path}[{i}]")
    elif "string" in types:
        assert isinstance(v, str), path
    elif "integer" in types:
        assert isinstance(v, int), path


def out(**kw):
    """A complete model answer: every property present, null where it does not apply."""
    base = {"outcome": "ANSWER", "metric": None, "dimensions": [], "period": None, "custom_start": None, "custom_end": None, "filters": [], "text_match": None,
            "breakdown_question": None, "clarify_question": None, "reason": None}
    return base | kw


def flt(dim, value, op="eq"):
    return {"dim": dim, "op": op, "value": value if isinstance(value, list) else [value]}


# ---- the schema --------------------------------------------------------------------------------------------------------------------------------
def test_the_schema_is_strict_compatible_and_has_no_refs_or_defaults():
    s = plan_schema()
    assert strict_compatible(s) and SCHEMAS["plan"] == s
    text = json.dumps(s)
    assert "$ref" not in text and "$defs" not in text and '"default"' not in text and '"title"' not in text and "anyOf" not in text


def test_every_queryplan_field_is_in_the_schema():
    """A new QueryPlan field that the schema lacks fails here: the model could never set it."""
    props = plan_schema()["properties"]
    assert set(QueryPlan.model_fields) - CODE_ONLY <= set(props), set(QueryPlan.model_fields) - CODE_ONLY - set(props)
    assert set(props) == (set(QueryPlan.model_fields) - CODE_ONLY) | MODEL_ONLY
    assert plan_schema()["required"] == list(props)


def test_the_closed_vocabularies_come_from_the_plan_itself():
    p = plan_schema()["properties"]
    assert set(p["metric"]["enum"]) == {m.value for m in MetricId} | {None}
    assert set(p["dimensions"]["items"]["enum"]) == {d.value for d in DimId}
    assert set(p["outcome"]["enum"]) >= {o.value for o in Outcome}
    assert "last_quarter" in p["period"]["enum"] and "custom" in p["period"]["enum"] and None in p["period"]["enum"]
    assert set(p["filters"]["items"]["properties"]) == {"dim", "op", "value"} and p["filters"]["items"]["properties"]["value"]["type"] == "array"


# ---- realistic model outputs: validate against the schema, compile to the expected plan --------------------------------------------------------
NPS = [flt("SURVEY", "s1"), flt("QUESTION", "nps")]
CASES = [
    ("How many responses did we get last month?", out(metric="RESPONSE_COUNT", period="last_month"),
     {"metric": "RESPONSE_COUNT", "start": date(2026, 9, 1), "end": date(2026, 9, 30)}),
    ("كم عدد الردود في الشهر الماضي؟", out(metric="RESPONSE_COUNT", period="last_month"),
     {"metric": "RESPONSE_COUNT", "start": date(2026, 9, 1), "end": date(2026, 9, 30)}),
    ("What is our NPS this quarter?", out(metric="NPS", period="this_quarter", filters=NPS),
     {"metric": "NPS", "start": date(2026, 10, 1), "end": TODAY, "survey": True, "question": "nps"}),
    ("ما هو صافي نقاط الترويج هذا الربع؟", out(metric="NPS", period="this_quarter", filters=NPS),
     {"metric": "NPS", "start": date(2026, 10, 1), "end": TODAY, "survey": True, "question": "nps"}),
    ("NPS by month over the last quarter", out(metric="NPS", dimensions=["MONTH"], period="last_quarter", filters=NPS),
     {"metric": "NPS", "dimensions": [DimId.MONTH], "start": date(2026, 7, 1), "end": date(2026, 9, 30), "survey": True, "question": "nps"}),
    ("Average rating this year by language", out(metric="AVG_RATING", dimensions=["LOCALE"], period="this_year", filters=[flt("SURVEY", "s1"), flt("QUESTION", "overall")]),
     {"metric": "AVG_RATING", "dimensions": [DimId.LOCALE], "start": date(2026, 1, 1), "end": TODAY, "survey": True, "question": "overall"}),
    ("متوسط التقييم حسب اللغة هذه السنة", out(metric="AVG_RATING", dimensions=["LOCALE"], period="this_year", filters=[flt("SURVEY", "s1"), flt("QUESTION", "overall")]),
     {"metric": "AVG_RATING", "dimensions": [DimId.LOCALE], "start": date(2026, 1, 1), "end": TODAY, "survey": True, "question": "overall"}),
    ("Completion rate in the last 7 days", out(metric="COMPLETION_RATE", period="last_7_days"),
     {"metric": "COMPLETION_RATE", "start": date(2026, 10, 18), "end": TODAY}),
    ("Responses per week in the last 30 days", out(metric="RESPONSE_COUNT", dimensions=["WEEK"], period="last_30_days"),
     {"metric": "RESPONSE_COUNT", "dimensions": [DimId.WEEK], "start": date(2026, 9, 25), "end": TODAY}),
    ("Responses between 1 March and 15 April 2026", out(metric="RESPONSE_COUNT", period="custom", custom_start="2026-03-01", custom_end="2026-04-15"),
     {"metric": "RESPONSE_COUNT", "start": date(2026, 3, 1), "end": date(2026, 4, 15)}),
    ("كم رداً بين 1 مارس و 15 أبريل 2026؟", out(metric="RESPONSE_COUNT", period="custom", custom_start="2026-03-01", custom_end="2026-04-15"),
     {"metric": "RESPONSE_COUNT", "start": date(2026, 3, 1), "end": date(2026, 4, 15)}),
    ("Arabic responses this month", out(metric="RESPONSE_COUNT", period="this_month", filters=[flt("LOCALE", "ar")]),
     {"metric": "RESPONSE_COUNT", "start": date(2026, 10, 1), "end": TODAY, "locale": "ar"}),
    ("Responses in English or Arabic this month", out(metric="RESPONSE_COUNT", period="this_month", filters=[flt("LOCALE", ["en", "ar"], "in")]),
     {"metric": "RESPONSE_COUNT", "start": date(2026, 10, 1), "end": TODAY, "locale": ["en", "ar"]}),
    ("How many answers mention parking or fees last month?", out(metric="RESPONSE_COUNT", period="last_month", text_match={"terms": ["parking", "fees"], "mode": "any"}),
     {"metric": "RESPONSE_COUNT", "start": date(2026, 9, 1), "end": date(2026, 9, 30), "terms": ["parking", "fees"]}),
    ("كم إجابة تذكر المصعد الشهر الماضي", out(metric="RESPONSE_COUNT", period="last_month", text_match={"terms": ["المصعد"], "mode": "any"}),
     {"metric": "RESPONSE_COUNT", "start": date(2026, 9, 1), "end": date(2026, 9, 30), "terms": ["المصعد"]}),
    ("Choice share of the unit type this year", out(metric="CHOICE_SHARE", period="this_year", filters=[flt("SURVEY", "s2"), flt("QUESTION", "kind")]),
     {"metric": "CHOICE_SHARE", "start": date(2026, 1, 1), "end": TODAY, "survey2": True, "question": "kind"}),
    ("Average rating by unit type last month", out(metric="AVG_RATING", period="last_month", filters=[flt("SURVEY", "s1"), flt("QUESTION", "overall")], breakdown_question="kind"),
     {"metric": "AVG_RATING", "start": date(2026, 9, 1), "end": date(2026, 9, 30), "survey": True, "question": "overall", "breakdown": "kind"}),
    ("Theme share for comments this quarter", out(metric="THEME_SHARE", period="this_quarter", filters=[flt("SURVEY", "s1"), flt("QUESTION", "comments")]),
     {"metric": "THEME_SHARE", "start": date(2026, 10, 1), "end": TODAY, "survey": True, "question": "comments"}),
    ("responses", out(metric="RESPONSE_COUNT"), {"metric": "RESPONSE_COUNT", "start": None, "end": None}),       # no period named: no dates, the compiler then asks which range
]


@pytest.mark.parametrize("text, raw, want", CASES, ids=[c[0][:40] for c in CASES])
def test_a_realistic_model_answer_validates_and_compiles_to_the_expected_plan(text, raw, want):
    conforms(plan_schema(), raw)                                                           # it is something strict mode could have produced
    checked = validate_output("plan", raw)                                                  # and the adapter's own check accepts it
    assert checked["metric"] == raw["metric"] or checked["metric"] is MetricId(raw["metric"])
    p = to_query_plan({k: v for k, v in checked.items() if v is not None}, TODAY, SURVEYS)
    assert p.outcome is Outcome.ANSWER and p.metric == MetricId(want["metric"])
    assert (p.date_range.start, p.date_range.end) == (want["start"], want["end"]) if want["start"] else p.date_range is None
    assert p.dimensions == want.get("dimensions", [])
    flts = {f.dim: f.value for f in p.filters}
    if want.get("survey"):
        assert flts[DimId.SURVEY] == str(SID)                                                # the opaque id became the real one
    if want.get("survey2"):
        assert flts[DimId.SURVEY] == SURVEYS["s2"]
    if want.get("question"):
        assert flts[DimId.QUESTION] == want["question"]
    if "locale" in want:
        assert flts[DimId.LOCALE] == want["locale"]
    assert (p.text_match.terms if p.text_match else None) == want.get("terms")
    assert p.breakdown_question == want.get("breakdown")


@pytest.mark.parametrize("raw", [
    out(outcome="CLARIFY", clarify_question="Which survey do you mean?"),
    out(outcome="CLARIFY", clarify_question="أي استبيان تقصد؟"),
    out(outcome="CANT_YET", reason="The data has no cost figures."),
    out(outcome="REFUSE", reason="That asks about one person."),
])
def test_non_answers_pass_through(raw):
    conforms(plan_schema(), raw)
    p = to_query_plan({k: v for k, v in validate_output("plan", raw).items() if v is not None}, TODAY, SURVEYS)
    assert p.outcome.value == raw["outcome"] and (p.clarify_question or p.reason)


# ---- what is not a plan ------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("raw", [
    out(metric="NPS", period="custom"),                                                    # custom needs both dates
    out(metric="NPS", period="custom", custom_start="2026-03-01"),
    out(metric="NPS", period="custom", custom_start="yesterday", custom_end="today"),
    out(metric="NPS", period="custom", custom_start="2026-04-15", custom_end="2026-03-01"),   # ends before it starts
    out(metric="NPS", period="custom", custom_start="2019-01-01", custom_end="2026-03-01"),   # longer than the allowed range
    out(metric="RESPONSE_COUNT", period="last_month", filters=[{"dim": "LOCALE", "op": "in", "value": []}]),
    "select 1", None, [],
])
def test_an_invalid_plan_is_rejected_not_guessed(raw):
    with pytest.raises(ValueError):                                                        # pydantic's ValidationError is a ValueError
        to_query_plan({k: v for k, v in raw.items() if v is not None} if isinstance(raw, dict) else raw, TODAY, SURVEYS)


def test_a_period_outside_the_list_or_a_metric_outside_the_catalogue_fails_the_adapter_check():
    for bad in (out(metric="NUKE"), out(metric="NPS", period="next_week"), out(outcome="EXECUTE")):
        with pytest.raises(ValueError):
            validate_output("plan", bad)
    assert OUTPUTS["plan"] is not None


def test_an_older_plan_with_date_range_still_works():
    p = to_query_plan({"metric": "RESPONSE_COUNT", "date_range": {"start": "2026-01-01", "end": "2026-01-31"}}, TODAY)
    assert (p.date_range.start, p.date_range.end) == (date(2026, 1, 1), date(2026, 1, 31))


def test_several_values_with_eq_mean_any_of_and_neq_with_several_is_rejected():
    p = to_query_plan(out(metric="RESPONSE_COUNT", period="this_year", filters=[flt("LOCALE", ["en", "ar"])]), TODAY, SURVEYS)
    assert (p.filters[0].op, p.filters[0].value) == ("in", ["en", "ar"])
    with pytest.raises(ValueError):
        to_query_plan(out(metric="RESPONSE_COUNT", period="this_year", filters=[flt("LOCALE", ["en", "ar"], "neq")]), TODAY, SURVEYS)


def test_the_outcome_is_the_one_field_that_is_never_null():
    assert plan_schema()["properties"]["outcome"] == {"type": "string", "enum": ["ANSWER", "CLARIFY", "CANT_YET", "REFUSE"]}
    with pytest.raises(ValueError):
        validate_output("plan", {})                                                        # an empty reply is a bad output, which the routes turn into their fallback


def test_an_unknown_survey_id_stays_as_written_and_the_compiler_rejects_it():
    p = to_query_plan(out(metric="NPS", period="this_year", filters=[flt("SURVEY", "s9"), flt("QUESTION", "nps")]), TODAY, SURVEYS)
    assert {f.dim: f.value for f in p.filters}[DimId.SURVEY] == "s9"


# ---- the catalogue and the follow-up context: no database ids, no respondent data ---------------------------------------------------------
def survey(i, qs=None, title=None):
    d = {"pages": [{"elements": qs or [{"type": "rating", "name": "nps", "title": "How likely to recommend?"}, {"type": "html", "name": "intro"},
                                     {"type": "comment", "name": "comments", "title": {"default": "Anything else?"}}]}]}
    return NS(id=uuid.uuid4(), title=json.dumps({"default": title or f"Survey {i}"}), defn=json.dumps(d))


UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def test_the_catalogue_has_opaque_ids_only_and_the_date():
    rows = [survey(i) for i in range(30)]
    cat, ids = ask_catalogue(rows, None, TODAY, "Asia/Dubai")
    assert not UUID.search(json.dumps(cat)) and cat["today"] == "2026-10-24" and cat["time_zone"] == "Asia/Dubai"
    assert len(cat["surveys"]) == 20 and list(ids) == [f"s{i}" for i in range(1, 21)] and ids["s1"] == str(rows[0].id)         # newest first, capped
    assert [q["id"] for q in cat["surveys"][0]["questions"]] == ["nps", "comments"]                                           # html is not a question
    assert {m["id"]: m["needs"] for m in cat["metrics"]}["NPS"] == ["SURVEY", "QUESTION"] and "selected_survey" not in cat


def test_the_selected_survey_is_always_in_the_catalogue_and_named():
    rows = [survey(i) for i in range(30)]
    cat, ids = ask_catalogue(rows, rows[25].id, TODAY, "Asia/Dubai")
    assert len(cat["surveys"]) == 20 and ids[cat["selected_survey"]] == str(rows[25].id)
    cat2, ids2 = ask_catalogue(rows, rows[3].id, TODAY, "UTC")
    assert ids2[cat2["selected_survey"]] == str(rows[3].id) and len(cat2["surveys"]) == 20


def test_titles_are_redacted_and_capped():
    cat, _ = ask_catalogue([survey(1, title="Call me on +971 50 123 4567 " + "x" * 200)], None, TODAY, "UTC")
    t = cat["surveys"][0]["title"]
    assert "123 4567" not in t and len(t) <= 80


def test_the_previous_plan_comes_back_in_the_models_terms():
    stored = QueryPlan.model_validate({"metric": "NPS", "date_range": {"start": "2026-07-01", "end": "2026-09-30"},
                                       "filters": [{"dim": "SURVEY", "op": "eq", "value": SURVEYS["s1"]}, {"dim": "QUESTION", "op": "eq", "value": "nps"}]}).model_dump_json()
    p = plan_for_model(stored, SURVEYS)
    assert not UUID.search(json.dumps(p)) and p["period"] == "custom" and (p["custom_start"], p["custom_end"]) == ("2026-07-01", "2026-09-30") and "date_range" not in p
    assert {f["dim"]: f["value"] for f in p["filters"]} == {"SURVEY": "s1", "QUESTION": "nps"}
    gone = plan_for_model(stored, {"s7": str(uuid.uuid4())})                              # a survey the model was not shown is left out, not leaked
    assert not UUID.search(json.dumps(gone)) and [f["dim"] for f in gone["filters"]] == ["QUESTION"]
    again = to_query_plan({**p, "metric": "NPS"}, TODAY, SURVEYS)                           # and it round-trips
    assert again.date_range.start == date(2026, 7, 1) and {f.dim: f.value for f in again.filters}[DimId.SURVEY] == SURVEYS["s1"]


# ---- the tidy rules and the cache key ---------------------------------------------------------------------------------------------------------
ALL = {SURVEYS["s1"], SURVEYS["s2"]}


def tidy(raw):
    return tidy_plan(to_query_plan(raw, TODAY, SURVEYS), ALL)


def test_a_survey_filter_naming_every_survey_is_no_filter_for_a_count():
    p = tidy(out(metric="RESPONSE_COUNT", period="last_month", filters=[flt("SURVEY", ["s1", "s2"], "in"), flt("LOCALE", "ar")]))
    assert [f.dim for f in p.filters] == [DimId.LOCALE]


def test_the_survey_filter_stays_when_the_metric_needs_it_or_names_only_some():
    needs = tidy(out(metric="NPS", period="last_month", filters=[flt("SURVEY", ["s1", "s2"], "in"), flt("QUESTION", "nps")]))
    assert [f.dim for f in needs.filters] == [DimId.SURVEY, DimId.QUESTION]
    some = tidy(out(metric="RESPONSE_COUNT", period="last_month", filters=[flt("SURVEY", "s1")]))
    assert [f.dim for f in some.filters] == [DimId.SURVEY]


def test_a_question_filter_the_compiler_cannot_use_is_dropped():
    count = tidy(out(metric="RESPONSE_COUNT", period="last_month", filters=[flt("QUESTION", "nps")]))
    assert count.filters == []
    search_list = tidy(out(metric="RESPONSE_COUNT", period="last_month", text_match={"terms": ["parking"], "mode": "any"}, filters=[flt("QUESTION", ["a", "b"], "in")]))
    assert search_list.filters == []
    search_one = tidy(out(metric="RESPONSE_COUNT", period="last_month", text_match={"terms": ["parking"], "mode": "any"}, filters=[flt("QUESTION", "comments")]))
    assert [f.dim for f in search_one.filters] == [DimId.QUESTION]                       # one question beside a search narrows it: kept
    rated = tidy(out(metric="AVG_RATING", period="last_month", filters=[flt("SURVEY", "s1"), flt("QUESTION", "overall")]))
    assert [f.dim for f in rated.filters] == [DimId.SURVEY, DimId.QUESTION]


def test_identical_filters_are_kept_once_and_a_clean_plan_is_returned_as_it_is():
    p = tidy(out(metric="RESPONSE_COUNT", period="last_month", filters=[flt("LOCALE", "ar"), flt("LOCALE", "ar")]))
    assert len(p.filters) == 1
    clean = to_query_plan(out(metric="RESPONSE_COUNT", period="last_month"), TODAY, SURVEYS)
    assert tidy_plan(clean, ALL) is clean


@pytest.mark.parametrize("a, b", [
    ("How many responses did we get last month?", "  how MANY responses did we get last month  "),
    ("How many responses did we get last month?", "How many responses did we get last month؟"),
    ("كم عدد الردود؟", "كم   عدد الردود"),
])
def test_equivalent_wordings_of_one_question_share_a_key(a, b):
    cat = {"today": "2026-10-24", "surveys": []}
    assert normalise_question(a) == normalise_question(b) and plan_key(a, cat, ["v1"]) == plan_key(b, cat, ["v1"])


def test_the_key_changes_with_the_question_the_catalogue_the_day_and_the_prompt():
    cat = {"today": "2026-10-24", "surveys": [{"id": "s1"}]}
    base = plan_key("responses last month", cat, ["prompt-1", "model-a"])
    assert plan_key("responses this month", cat, ["prompt-1", "model-a"]) != base
    assert plan_key("responses last month", cat | {"today": "2026-10-25"}, ["prompt-1", "model-a"]) != base
    assert plan_key("responses last month", cat | {"surveys": [{"id": "s1"}, {"id": "s2"}]}, ["prompt-1", "model-a"]) != base
    assert plan_key("responses last month", cat, ["prompt-2", "model-a"]) != base and plan_key("responses last month", cat, ["prompt-1", "model-b"]) != base
    assert plan_key("responses last month", cat, ["prompt-1", "model-a"]) == base
