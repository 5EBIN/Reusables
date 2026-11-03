from datetime import UTC, datetime, timedelta

import pytest

from app.core.quality import RuleError, evaluate, gibberish, should_exclude, validate_rules

T = datetime(2026, 10, 7, 12, tzinfo=UTC)


def R(i, **k): return {"id": i, "secs": 100, "device": None, "ratings": [1, 2, 3], "texts": [], "attn": None, "at": T, **k}


@pytest.mark.parametrize("bad", [{"nope": {}}, {"speeder": {"treatment": "delete"}}, {"speeder": {"pct": 2}}, {"speeder": {"pct": 95}}, {"speeder": {"pct": "35"}}, {"speeder": {"pct": True}},
                                 {"straightline": {"min_rows": 1}}, {"duplicate_device": {"count": 1}}, {"duplicate_device": {"window_h": 0}}, {"gibberish": {"pct": 5}}, {"attention": {"question": ""}},
                                 {"attention": {"expected": 5}}, "x", {"speeder": "x"}])
def test_rule_rejections(bad):
    with pytest.raises(RuleError):
        validate_rules(bad)


def test_defaults_and_override():
    r = validate_rules({"speeder": {"pct": 50}, "gibberish": {"treatment": "exclude"}})
    assert r["speeder"]["pct"] == 50 and r["gibberish"]["treatment"] == "exclude" and r["duplicate_device"]["count"] == 3


@pytest.mark.parametrize("t,exp", [("aaaaaaa", True), ("asdfghjkl", True), ("bcdfghjk", True), ("ممممممممم", True), ("Parking is hard on weekends", False), ("مواقف السيارات صعبة", False), ("ok", False), ("x" * 50, True),
                                   ("qwrtpsdfgh", True), ("The parking, however, is nice", False)])
def test_gibberish(t, exp):
    assert gibberish(t) is exp


def test_speeder_needs_enough_data_and_median():
    rules = validate_rules({})
    assert evaluate([R(str(i), secs=100) for i in range(3)] + [R("fast", secs=5)], rules) == {}                    # fewer than 5 timed responses -> no median, no speeder call
    rs = [R(str(i), secs=100) for i in range(6)] + [R("fast", secs=30), R("edge", secs=35)]
    f = evaluate(rs, rules)
    assert f["fast"] == ["speeder"] and "edge" not in f


def test_straightline_attention_duplicates():
    rules = validate_rules({"attention": {"question": "q6", "expected": "3"}})
    rs = [R("a", ratings=[4] * 8), R("b", ratings=[4] * 7), R("c", attn="2"), R("d", attn="3")]
    f = evaluate(rs, rules)
    assert f["a"] == ["straightline"] and "b" not in f and f["c"] == ["attention"] and "d" not in f
    dup = [R(f"d{i}", device="h1", at=T + timedelta(hours=i * 5)) for i in range(3)] + [R("far", device="h1", at=T + timedelta(days=5)), R("other", device="h2")]
    f = evaluate(dup, validate_rules({}))
    assert {k for k, v in f.items() if "duplicate_device" in v} == {"d0", "d1", "d2"}


def test_treatment_exclusion_and_off():
    rules = validate_rules({"speeder": {"treatment": "off"}})
    rs = [R(str(i)) for i in range(6)] + [R("fast", secs=1)]
    assert evaluate(rs, rules) == {}
    r2 = validate_rules({})
    assert should_exclude(["straightline"], r2) is None and should_exclude(["straightline", "speeder"], r2) == "speeder"
