import json

import httpx
import pytest

from app.adapters.llm_openai_compat import OpenAICompatLLM
from app.core.sentiment import LABELS, Scored, SentimentError, from_lexicon, from_model, golden_report, golden_rows, shown_label, summarize


def test_lexicon_labels_english_arabic_and_gibberish():
    got = from_lexicon(["The staff were great and helpful", "terrible and slow service", "ممتاز", "...", "the lift is on the 3rd floor"])
    assert [s.label for s in got] == [1, -1, 1, 0, 0]
    assert got[3].confidence == 0.0 and all(s.source == "lexicon" for s in got)       # gibberish: neutral, zero confidence


def test_from_model_accepts_a_valid_answer():
    got = from_model(["a", "b"], [{"label": "positive", "confidence": 0.9}, {"label": "negative", "confidence": 1}])
    assert [(s.label, s.confidence, s.source) for s in got] == [(1, 0.9, "model"), (-1, 1.0, "model")]


@pytest.mark.parametrize("raw", [
    None, {}, [], [{"label": "positive", "confidence": 0.9}],                                  # not a list, or wrong count
    [{"label": "happy", "confidence": 0.9}, {"label": "neutral", "confidence": 0.5}],          # unknown label
    [{"label": "positive", "confidence": 1.5}, {"label": "neutral", "confidence": 0.5}],       # confidence out of range
    [{"label": "positive", "confidence": True}, {"label": "neutral", "confidence": 0.5}],      # a bool is not a number
    [{"label": "positive"}, {"label": "neutral", "confidence": 0.5}],                          # missing confidence
    ["positive", "neutral"],
])
def test_from_model_rejects_unusable_output(raw):
    with pytest.raises(SentimentError):
        from_model(["a", "b"], raw)


def test_weak_labels_are_counted_as_low_confidence():
    assert shown_label(1, 0.59) == "low_confidence" and shown_label(1, 0.6) == "positive" and shown_label(-1, 0.9) == "negative"


def test_summary_counts_and_shares():
    s = summarize([(1, 0.9), (1, 0.8), (-1, 0.9), (0, 0.7), (1, 0.2)], 5)
    assert s["counts"] == {"positive": 2, "neutral": 1, "negative": 1, "low_confidence": 1}
    assert s["positive_pct"] == 40.0 and s["negative_pct"] == 20.0 and s["net"] == 20.0 and not s["suppressed"]


def test_summary_hides_the_breakdown_below_the_minimum_group():
    s = summarize([(1, 0.9), (-1, 0.9), (0, 0.9), (1, 0.9)], 5)
    assert s == {"n": 4, "suppressed": True, "note": "Fewer than 5 answers: breakdown hidden."}


async def test_adapter_sends_texts_and_returns_results():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        results = [{"id": 0, "label": "negative", "confidence": 0.8}, {"id": 1, "label": "positive", "confidence": 0.95}]
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"results": results})}}], "usage": {}})

    llm = OpenAICompatLLM("https://x.example/v1", "m", transport=httpx.MockTransport(handler))
    out = await llm.classify_sentiment(["الخدمة سيئة", "great"])
    body = seen[0]
    assert body["response_format"]["json_schema"]["name"] == "sentiment" and "الخدمة سيئة" in body["messages"][1]["content"]
    assert [s.label for s in from_model(["a", "b"], out)] == [-1, 1]


def test_golden_set_is_well_formed():
    rows = golden_rows()
    assert len(rows) >= 30 and {r["lang"] for r in rows} == {"en", "ar"} and {r["label"] for r in rows} == set(LABELS)
    assert all(sum(1 for r in rows if r["lang"] == lang and r["label"] == label) >= 3 for lang in ("en", "ar") for label in LABELS)     # every cell has examples


def test_golden_report_with_a_perfect_and_a_word_list_classifier():
    truth = {r["text"]: r["label"] for r in golden_rows()}
    perfect = golden_report(lambda texts: [Scored(LABELS[truth[t]], 0.9, "model") for t in texts])
    assert perfect["accuracy"] == 1.0 and perfect["accuracy_by_language"] == {"ar": 1.0, "en": 1.0}
    assert perfect["by_confidence"][2]["n"] == perfect["n"] and perfect["by_confidence"][0]["accuracy"] is None      # empty bucket has no accuracy
    weak = golden_report(from_lexicon, batch=7)                       # batch size must not change the shape of the report
    assert weak["n"] == perfect["n"] and 0 <= weak["accuracy"] < 1 and sum(b["n"] for b in weak["by_confidence"]) == weak["n"]


def test_golden_report_does_not_depend_on_batch_size():
    assert golden_report(from_lexicon, batch=1) == golden_report(from_lexicon, batch=50)


def test_results_with_ids_are_matched_by_id_even_when_reordered():
    raw = [{"id": 1, "label": "negative", "confidence": 0.9}, {"id": 0, "label": "positive", "confidence": 0.8}]
    assert [s.label for s in from_model(["a", "b"], raw)] == [1, -1]


@pytest.mark.parametrize("raw", [
    [{"id": 0, "label": "positive", "confidence": 0.9}, {"id": 0, "label": "negative", "confidence": 0.9}],     # duplicate id
    [{"id": 0, "label": "positive", "confidence": 0.9}, {"id": 5, "label": "negative", "confidence": 0.9}],     # unknown id
    [{"id": 0, "label": "positive", "confidence": 0.9}, {"label": "negative", "confidence": 0.9}],              # one id missing
    [{"id": "0", "label": "positive", "confidence": 0.9}, {"id": "1", "label": "negative", "confidence": 0.9}],  # ids must be integers
])
def test_bad_ids_are_rejected(raw):
    with pytest.raises(SentimentError):
        from_model(["a", "b"], raw)


@pytest.mark.parametrize("text,label", [
    ("not good", -1), ("This was not bad at all", 1), ("No complaints, everything is great", 1), ("no problems ever", 1), ("it is not slow", 1),
    ("not helpful", -1), ("to die for", 1), ("a waste of money", -1),
    ("sooooo goooood", 1), ("ممتاااااز", 1), ("الخدمة مو ممتازة", -1), ("ما في مشاكل", 1),
])
def test_word_list_handles_negation_phrases_and_stretched_letters(text, label):
    assert from_lexicon([text])[0].label == label


def test_negation_only_reaches_a_few_words_back():
    assert from_lexicon(["not that i would say anything about the service but it was great"])[0].label == 1


async def test_adapter_caps_long_answers_and_sends_ids():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content)["messages"][1]["content"])
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"results": []})}}], "usage": {}})

    llm = OpenAICompatLLM("https://x.example/v1", "m", transport=httpx.MockTransport(handler))
    await llm.classify_sentiment(["x" * 50_000, "short"], hint="wrong number of results")
    payload = seen[0]
    assert '"id": 0' in payload and '"id": 1' in payload and payload.count("x") <= 2_100 and "wrong number of results" in payload
