"""One model for a theme proposal: the schema the model answers to, the validation of its answer and what the route stores."""
import pytest

import app.adapters.llm_task_definitions  # noqa: F401  (registers the example tasks)
from app.adapters.llm_tasks import SCHEMAS, strict_compatible
from app.core.themes import ThemeProposal, json_schema, valid_proposals

GOOD = {"key": "parking_fees", "label": {"en": "Parking and fees", "ar": "المواقف والرسوم"}, "definition": "Cost and availability of parking.", "keywords": ["parking", "مواقف", "fees"]}


def test_the_schema_is_derived_from_the_model_and_is_strict_compatible():
    sch = json_schema()
    assert SCHEMAS["themes"] == sch and strict_compatible(sch)
    theme = sch["properties"]["themes"]["items"]
    assert set(theme["properties"]) == {"key", "label", "definition", "keywords"} == set(theme["required"])
    assert set(theme["properties"]["label"]["properties"]) == {"en", "ar"} == set(theme["properties"]["label"]["required"])
    assert "$ref" not in str(sch) and "$defs" not in str(sch)


def test_the_schemas_own_example_goes_through_the_route_validation():
    assert valid_proposals([GOOD]) == [{**GOOD}]
    assert valid_proposals([{**GOOD, "label": {"en": "Parking", "ar": None}}])[0]["label"] == {"en": "Parking", "ar": None}
    assert valid_proposals([{**GOOD, "label": {"en": "Parking"}}])                                         # a stored/test proposal may leave the Arabic name out


@pytest.mark.parametrize("bad", [
    {**GOOD, "key": "other"}, {**GOOD, "key": "unclassified"}, {**GOOD, "key": "!!"}, {**GOOD, "keywords": []}, {**GOOD, "keywords": ["x"] * 21}, {**GOOD, "label": "Parking"},
    {**GOOD, "label": {"ar": "x"}}, {**GOOD, "definition": "d" * 501}, {**GOOD, "extra": 1}, "text", None, {**GOOD, "keywords": "parking"},
])
def test_invalid_proposals_are_dropped(bad):
    assert valid_proposals([bad]) == []


def test_a_spelling_of_the_key_is_normalised_and_each_proposal_is_judged_alone():
    out = valid_proposals([{**GOOD, "key": "Parking Fees"}, {**GOOD, "key": "other"}, {**GOOD, "key": "noise", "keywords": ["noise"], "label": {"en": "Noise"}}, {**GOOD, "key": "parking-fees"}])
    assert [t["key"] for t in out] == ["parking_fees", "noise"]                                              # the duplicate after normalising is dropped too
    assert ThemeProposal.model_validate({**GOOD, "keywords": [" a ", "", "b" * 90]}).keywords == ["a", "b" * 60]
