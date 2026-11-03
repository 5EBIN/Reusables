"""Deterministic text-analysis core: theme classification (enum only), sentiment, quotes, language, stats."""
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from app.core.lexicon import evidence, verdict
from app.core.normalize_ar import ar_norm

OTHER, UNCLASSIFIED = "other", "unclassified"
LOW_CONF = 0.6


@dataclass
class Theme:
    key: str
    label: dict
    keywords: list[str] = field(default_factory=list)


@dataclass
class ThemeResult:
    themes: list[str]
    unclassified: bool = False
    sentiment: int = 0          # -1, 0, 1
    confidence: float = 0.5
    low_confidence: bool = False


class ThemeClassifier(Protocol):
    version: str
    def classify(self, texts: list[str]) -> list[ThemeResult]: ...


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", ar_norm(text or "").lower()).strip()


def informative(text: str) -> bool:
    letters = re.findall(r"[^\W\d_]", text or "", flags=re.UNICODE)
    return len(letters) >= 3 and len(set(letters)) >= 2


# Word-list sentiment lives in app.core.lexicon (the words are data: app/data/sentiment_lexicon.json).
_STRETCH_AR = re.compile(r"([\u0600-\u06FF])\1{2,}")      # Arabic letters rarely double: stretched letters collapse to one
_STRETCH = re.compile(r"(.)\1{2,}")                         # soooo -> soo


def _clean(text: str) -> str:
    return _STRETCH.sub(r"\1\1", _STRETCH_AR.sub(r"\1", norm(text)))


def sentiment(text: str) -> tuple[int, float]:
    """Word-list sentiment (negation, fixed phrases, intensity, stretched letters). Ties/no signal -> neutral with confidence below LOW_CONF (shown neutral + flagged)."""
    return verdict(*evidence(_clean(text)))


_ARABIC = re.compile(r"[؀-ۿ]")
_AR_PREFIX = r"(?:[وف])?(?:لل|[بلك]?(?:ال)?)"   # و/ف, then لل or ب/ل/ك, then ال: each optional, in that order


_EN_SUFFIX = r"(?:s|es|ed|ing|er|ers|ly)?"                                                       # price -> prices, clean -> cleaning
_AR_SUFFIX = r"(?:ون|ين|ات|ان|ها|هم|كم|نا|[هكي])?"   # ون ين ات ان ها هم كم نا ه ك ي (plural and attached pronouns; ة is already ه after norm)


def keyword_pattern(kw: str) -> re.Pattern:
    """A keyword matches as a whole word, not inside another word ("rude" is not in "prudent", "gate" not in "investigate"). Written with a trailing `*` it is a stem
    ("plumb*" matches plumbing). Otherwise only a short list of endings may follow (English: s es ed ing er ers ly; Arabic: plural and attached pronouns), and in Arabic
    the attached particles (و ف ب ل ك ال, as in وبالصيانة) may come before the word. They are listed explicitly because a plain word-boundary test does not see them."""
    stem = kw.endswith("*")
    kw = kw.rstrip("*").strip()
    arabic = bool(_ARABIC.match(kw))
    tail = r"\w*" if stem else (_AR_SUFFIX if arabic else _EN_SUFFIX)
    return re.compile(rf"(?<!\w){_AR_PREFIX if arabic else ''}{re.escape(kw)}{tail}(?!\w)")


class KeywordClassifier:
    """Deterministic. Unmatched text -> 'other'; empty/gibberish -> 'unclassified' (never reassigned to a big theme)."""
    def __init__(self, themes: list[Theme], multi_label: bool = True, version: str = "kw-1.0"):
        self.themes = [(t.key, [keyword_pattern(norm(k)) for k in t.keywords if k.strip()]) for t in themes]
        self.multi_label, self.version = multi_label, version

    def one(self, text: str) -> ThemeResult:
        if not informative(text):
            return ThemeResult([], True, 0, 0.0, True)
        t = norm(text)
        hits = [k for k, kws in self.themes if any(kw.search(t) for kw in kws)]
        if not self.multi_label:
            hits = hits[:1]
        s, c = sentiment(text)
        low = c < LOW_CONF
        return ThemeResult(hits or [OTHER], False, 0 if low else s, c, low)

    def classify(self, texts):
        return [self.one(x) for x in texts]


class LLMThemeClassifier:
    """Wraps an LLM that proposes theme ids; anything outside the frozen list becomes 'other'."""
    def __init__(self, picks, themes: list[Theme], version: str):
        self.picks, self.allowed, self.version = picks, {t.key for t in themes}, version

    def classify(self, texts):
        out = []
        for text, pick in zip(texts, self.picks(texts), strict=True):
            if not informative(text):
                out.append(ThemeResult([], True, 0, 0.0, True))
                continue
            ids = [p for p in (pick if isinstance(pick, list) else [pick]) if p in self.allowed]
            s, c = sentiment(text)
            out.append(ThemeResult(ids or [OTHER], False, 0 if c < LOW_CONF else s, c, c < LOW_CONF))
        return out


def script_of(text: str) -> str:
    ar = len(re.findall(r"[؀-ۿ]", text))
    la = len(re.findall(r"[A-Za-z]", text))
    if ar and la and min(ar, la) / max(ar, la) > 0.25:
        return "mixed"
    return "ar" if ar > la else "en"


def select_quotes(items: list[tuple[str, str, list[str]]], theme: str, seed: str, k: int = 3) -> list[dict]:
    """Deterministic, stratified by seeded hash. Every quote is a verbatim response text (verified)."""
    pool = [(rid, txt) for rid, txt, th in items if theme in th and txt]
    pool.sort(key=lambda x: hashlib.sha256(f"{seed}|{theme}|{x[0]}".encode()).hexdigest())
    out = []
    for rid, txt in pool[:k]:
        assert txt in dict(pool).values()
        out.append({"response_id": rid, "text": txt, "script": script_of(txt)})
    return out


def _terciles(values: list[float]) -> tuple[float, float] | None:
    v = sorted(values)
    return (v[len(v) // 3], v[(2 * len(v)) // 3]) if len(v) >= 3 else None


def _band(x: float | None, cuts: tuple[float, float] | None) -> str:
    if x is None or cuts is None:
        return "none"
    return "low" if x < cuts[0] else "mid" if x < cuts[1] else "high"


def stratified_sample(rows: list[dict], k: int, seed: str) -> list[dict]:
    """The answers the model reads when proposing themes: spread over language, month, rating band and length band, so the first rows in the database (one language, one
    month) are not the only voices. `rows` carry id, text, locale, month ("YYYY-MM") and rating (number or None). Bands are terciles of the data itself, so they work for any
    scale. Each stratum gets a share of k in proportion to its size (at least one while k allows); inside a stratum the order is a seeded hash. The result depends on the
    rows and the seed, never on their order."""
    if len(rows) <= k:
        return sorted(rows, key=lambda r: r["id"])
    rc, lc = _terciles([r["rating"] for r in rows if r.get("rating") is not None]), _terciles([float(len(r["text"])) for r in rows])
    strata: dict[tuple, list[dict]] = {}
    for r in rows:
        strata.setdefault((r["locale"], r["month"], _band(r.get("rating"), rc), _band(float(len(r["text"])), lc)), []).append(r)
    h = lambda *p: hashlib.sha256("|".join(map(str, p)).encode()).hexdigest()  # noqa: E731
    keys = sorted(strata, key=lambda s: h(seed, *s))
    take = {s: 0 for s in keys}
    if len(keys) >= k:
        for s in keys[:k]:
            take[s] = 1
    else:
        quota = {s: k * len(strata[s]) / len(rows) for s in keys}
        take = {s: min(len(strata[s]), max(1, int(quota[s]))) for s in keys}
        for s in sorted(keys, key=lambda s: (-(quota[s] - int(quota[s])), h(seed, *s))):
            if sum(take.values()) >= k:
                break
            if take[s] < len(strata[s]):
                take[s] += 1
        for s in sorted(keys, key=lambda s: (-take[s], h(seed, *s))):                    # the at-least-one rule can overshoot k: trim the largest shares
            if sum(take.values()) <= k:
                break
            if take[s] > 1:
                take[s] -= 1
    out = [r for s in keys for r in sorted(strata[s], key=lambda r: h(seed, s, r["id"]))[: take[s]]]
    return sorted(out, key=lambda r: h(seed, r["id"]))[:k]


def pearson(xs: list[float], ys: list[float], min_n: int = 30) -> float | None:
    n = len(xs)
    if n < min_n or n != len(ys):
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    return round(sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / (sx * sy), 4)


GOLDEN_PATH = Path(__file__).resolve().parent.parent / "data" / "golden_ar_en.jsonl"
DEMO_THEMES = [
    Theme("service_staff", {"en": "Service and staff", "ar": "الخدمة والموظفون"},
          ["staff", "service", "team", "helpful", "reception", "الموظف", "خدمة", "الخدمه", "فريق", "متعاون", "استقبال"]),
    Theme("maintenance", {"en": "Maintenance", "ar": "الصيانة"},
          ["maintenance", "repair", "plumb*", "fix", "leak", "الصيانه", "صيانه", "اصلاح", "تسريب"]),
    Theme("parking", {"en": "Parking", "ar": "المواقف"},
          ["parking", "park ", "موقف", "مواقف", "الباركينج"]),
    Theme("price", {"en": "Price and fees", "ar": "الأسعار والرسوم"},
          ["price", "fee", "expensive", "cost", "rent increase", "سعر", "اسعار", "رسوم", "غالي", "تكلفه"]),
    Theme("facilities", {"en": "Facilities", "ar": "المرافق"},
          ["gym", "pool", "facilit*", "playground", "elevator", "مسبح", "نادي", "مرافق", "مصعد"]),
    Theme("cleanliness", {"en": "Cleanliness", "ar": "النظافة"},
          ["clean", "dirty", "trash", "garbage", "نظاف", "قذر", "قمامه"]),
    Theme("noise", {"en": "Noise", "ar": "الضوضاء"},
          ["noise", "noisy", "drilling", "loud", "ضوضاء", "ازعاج", "صوت عال"]),
]


GATE = {"en": 0.85, "ar": 0.85, "other_max": 0.15}
GATE_MIN_ANSWERS = 20                      # below this the "other" rate says nothing


def golden_report(classifier=None, rows: list[dict] | None = None) -> dict:
    """Accuracy per language and 'other' rate on labelled rows ({lang, text, themes}); the committed demo set and the demo themes unless told otherwise."""
    clf = classifier or KeywordClassifier(DEMO_THEMES)
    rows = rows if rows is not None else [json.loads(line) for line in GOLDEN_PATH.read_text(encoding="utf8").splitlines() if line.strip()]
    res = clf.classify([r["text"] for r in rows])
    by = {"en": [0, 0], "ar": [0, 0]}
    others = 0
    for r, x in zip(rows, res, strict=True):
        lang = r["lang"]
        ok = set(x.themes) == set(r["themes"]) and x.unclassified == r.get("unclassified", False)
        by[lang][0] += ok
        by[lang][1] += 1
        others += OTHER in x.themes
    n = len(rows)
    return {"n": n, "accuracy_en": by["en"][0] / by["en"][1] if by["en"][1] else None, "accuracy_ar": by["ar"][0] / by["ar"][1] if by["ar"][1] else None,
            "other_rate": others / n, "gates": GATE}


def gate_from_results(results: list[ThemeResult], acc: dict | None = None) -> dict:
    """The gate for ONE organisation's taxonomy, measured on that organisation's own answers (not on the demo themes). `status`: "fail" when more than 15% of its
    answers land in "other", or when accuracy is known (`acc`, from labelled rows {lang, text, themes}: the review queue produces them) and a language scores under 85%;
    "pass" when it is measured and neither happens; "unevaluated" when there are too few answers. Accuracy is None until labelled rows exist."""
    res = [r for r in results if not r.unclassified]
    other = (sum(OTHER in r.themes for r in res) / len(res)) if res else None
    failing = (other is not None and len(res) >= GATE_MIN_ANSWERS and other > GATE["other_max"]) or bool(
        acc and any(acc[k] is not None and acc[k] < GATE[k[-2:]] for k in ("accuracy_en", "accuracy_ar")))
    measured = len(res) >= GATE_MIN_ANSWERS or acc is not None
    return {"status": "fail" if failing else "pass" if measured else "unevaluated", "answers": len(res), "other_rate": other,
            "accuracy_en": acc and acc["accuracy_en"], "accuracy_ar": acc and acc["accuracy_ar"], "gates": GATE}


def taxonomy_gate(classifier, texts: list[str], gold: list[dict] | None = None) -> dict:
    """The gate for a classifier that has not tagged anything yet: its results on the organisation's answers (and on labelled rows, when there are any)."""
    return gate_from_results(classifier.classify(texts), golden_report(classifier, gold) if gold else None)
