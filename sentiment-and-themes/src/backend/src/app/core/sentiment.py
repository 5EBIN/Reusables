"""Sentiment of open-text answers: checking what a model returned, the word-list fallback, and the summary the screen shows. Pure functions, no I/O.

A model result is only trusted when it has exactly one entry per text, a known label and a confidence between 0 and 1; anything else is rejected and the
caller falls back to the word list (app.core.text_analysis.sentiment). Labels are stored as -1, 0, 1. Below LOW_CONF a label is shown as neutral and flagged,
the same rule the theme tagging uses."""
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.text_analysis import LOW_CONF, informative, sentiment as lexicon_sentiment

LABELS = {"negative": -1, "neutral": 0, "positive": 1}
NAMES = {v: k for k, v in LABELS.items()}
MAX_BATCH = 50


class SentimentError(Exception):
    """The model output cannot be used."""


@dataclass(frozen=True)
class Scored:
    label: int          # -1, 0, 1
    confidence: float   # 0..1
    source: str         # 'model' | 'lexicon'


def from_lexicon(texts: list[str]) -> list[Scored]:
    out = []
    for t in texts:
        if not informative(t):
            out.append(Scored(0, 0.0, "lexicon"))
            continue
        label, conf = lexicon_sentiment(t)
        out.append(Scored(label, conf, "lexicon"))
    return out


def from_model(texts: list[str], raw: Any) -> list[Scored]:
    """Validates the model's answer: a list with one {label, confidence} per text. When the results carry an `id` (the text's position), they are
    matched by id, so a reordered answer is put right; a duplicate, missing or unknown id is rejected. Without ids the order is trusted."""
    if not isinstance(raw, list) or len(raw) != len(texts):
        raise SentimentError("wrong number of results")
    if any(not isinstance(item, dict) for item in raw):
        raise SentimentError("each result must be an object")
    ids = [item.get("id") for item in raw]
    if any(i is not None for i in ids):
        if any(isinstance(i, bool) or not isinstance(i, int) for i in ids) or sorted(ids) != list(range(len(texts))):
            raise SentimentError("ids must be 0..n-1, each once")
        raw = sorted(raw, key=lambda item: item["id"])
    out = []
    for item in raw:
        if item.get("label") not in LABELS:
            raise SentimentError("unknown label")
        conf = item.get("confidence")
        if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
            raise SentimentError("bad confidence")
        out.append(Scored(LABELS[item["label"]], float(conf), "model"))
    return out


def shown_label(label: int, confidence: float) -> str:
    """What the screen counts: a weak label is shown as neutral."""
    return "low_confidence" if confidence < LOW_CONF else NAMES[label]


def summarize(rows: list[tuple[int, float]], min_group: int) -> dict:
    """Counts and shares for a set of (label, confidence). With fewer than `min_group` answers only the total is returned, so a handful of
    answers cannot be traced to a person."""
    n = len(rows)
    if n < min_group:
        return {"n": n, "suppressed": True, "note": f"Fewer than {min_group} answers: breakdown hidden."}
    counts = {"positive": 0, "neutral": 0, "negative": 0, "low_confidence": 0}
    for label, conf in rows:
        counts[shown_label(label, conf)] += 1
    pct = lambda k: round(100 * counts[k] / n, 1) if n else None      # noqa: E731
    return {"n": n, "suppressed": False, "counts": counts, "positive_pct": pct("positive"), "negative_pct": pct("negative"),
            "net": round((counts["positive"] - counts["negative"]) * 100 / n, 1) if n else None,
            "note": f"Answers with confidence below {LOW_CONF} are counted as low_confidence."}


GOLDEN_PATH = Path(__file__).resolve().parent.parent / "data" / "golden_sentiment.jsonl"
BUCKETS = ((0.0, LOW_CONF), (LOW_CONF, 0.8), (0.8, 1.01))


SURVEY_PATH = GOLDEN_PATH.with_name("golden_sentiment_survey.jsonl")       # survey-style comments across sectors; a second set so the word list is not judged only on the text it was built beside
SETS = {"core": GOLDEN_PATH, "survey": SURVEY_PATH}


def golden_rows(which: str = "core") -> list[dict]:
    return [json.loads(line) for line in SETS[which].read_text(encoding="utf8").splitlines() if line.strip()]


def golden_report(predict: Callable[[list[str]], list[Scored]], batch: int = MAX_BATCH, which: str = "core") -> dict:
    """Scores a classifier on the labelled English and Arabic set (Gulf dialect, mixed and sarcastic cases included).
    Reports accuracy per language and, because a model's own confidence is not calibrated, the accuracy inside each confidence bucket:
    a trustworthy classifier is more accurate in the higher buckets. `batch` lets you check that the label does not depend on batch size."""
    rows = golden_rows(which)
    got: list[Scored] = []
    for i in range(0, len(rows), batch):
        got += predict([r["text"] for r in rows[i:i + batch]])
    ok = [NAMES[g.label] == r["label"] for g, r in zip(got, rows, strict=True)]
    by_lang: dict[str, list[bool]] = {}
    for r, hit in zip(rows, ok, strict=True):
        by_lang.setdefault(r["lang"], []).append(hit)
    buckets = []
    for lo, hi in BUCKETS:
        hits = [hit for g, hit in zip(got, ok, strict=True) if lo <= g.confidence < hi]
        buckets.append({"from": lo, "to": min(hi, 1.0), "n": len(hits), "accuracy": round(sum(hits) / len(hits), 3) if hits else None})
    return {"n": len(rows), "accuracy": round(sum(ok) / len(ok), 3), "accuracy_by_language": {k: round(sum(v) / len(v), 3) for k, v in sorted(by_lang.items())},
            "by_confidence": buckets}
