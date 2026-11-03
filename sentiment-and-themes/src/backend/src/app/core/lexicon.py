"""The survey sentiment word list: loading it (data/sentiment_lexicon.json) and scoring a text with it.

Matching is by whole word, so "chocolate" never counts as "late". English words also match their usual endings (s, es, ed, d, ing, ly, est); Arabic words match with
the usual attached prefixes (و ف ب ل ك ال) and endings. The score of a text is built from:
  - fixed phrases ("no complaints" is praise although "complaints" is negative), taken out of the text first;
  - single words, weight 2 (strong) or 1 (mild);
  - negation: a negator within three words before a word flips it ("not helpful" is negative, "no problems" is positive);
  - intensity: a booster next to a word ("very", "جدا") raises its weight by half, a dampener ("slightly", "شوي") halves it.
The word list is data, not code: edit the JSON file, then run scripts/eval_sentiment.py to see the effect."""
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.normalize_ar import ar_norm

PATH = Path(__file__).resolve().parent.parent / "data" / "sentiment_lexicon.json"
WINDOW = 3                                              # a negator this many words before a sentiment word flips it
BOOST, DAMPEN = 1.5, 0.5
MIXED_GAP = 2.0                                         # positive and negative evidence closer than this is "mixed": no confident polarity
_ARABIC = re.compile(r"[؀-ۿ]")
_EN_ENDINGS = "(?:s|es|ed|d|ing|ly|est)?"
_AR_PREFIX = "(?:وال|بال|كال|فال|لل|ال|و|ف|ب|ل|ك)?"
_AR_ENDING = "(?:ها|هم|ات|ين|ون|ه|ا)?"


def _n(s: str) -> str:
    return re.sub(r"\s+", " ", ar_norm(s).lower()).strip()


@dataclass(frozen=True)
class Entry:
    pattern: re.Pattern
    weight: int
    positive: bool
    arabic: bool


@dataclass(frozen=True)
class Lexicon:
    version: str
    phrases: tuple[Entry, ...]
    words: tuple[Entry, ...]
    negators: frozenset[str]
    boosters: frozenset[str]
    dampeners: frozenset[str]


def _pattern(text: str) -> tuple[re.Pattern, bool]:
    w = _n(text)
    if _ARABIC.search(w):
        return re.compile(r"(?<![؀-ۿ])" + _AR_PREFIX + re.escape(w) + _AR_ENDING + r"(?![؀-ۿ])"), True
    return re.compile(r"(?<![a-z0-9'])" + re.escape(w) + _EN_ENDINGS + r"(?![a-z0-9'])"), False


@lru_cache(maxsize=1)
def load() -> Lexicon:
    d = json.loads(PATH.read_text(encoding="utf-8"))
    words: list[Entry] = []
    phrases: list[tuple[int, Entry]] = []
    negators, boosters, dampeners = set(), set(), set()
    for lang in ("en", "ar"):
        part = d[lang]
        for key, weight, positive in (("pos_strong", 2, True), ("pos", 1, True), ("neg_strong", 2, False), ("neg", 1, False)):
            for w in part[key]:
                pat, arabic = _pattern(w)
                words.append(Entry(pat, weight, positive, arabic))
        for key, positive in (("pos", True), ("neg", False)):
            for text, weight in part["phrases"][key]:
                pat, arabic = _pattern(text)
                phrases.append((len(text), Entry(pat, weight, positive, arabic)))
        negators |= {_n(x) for x in part["negators"]}
        boosters |= {_n(x) for x in part["boosters"]}
        dampeners |= {_n(x) for x in part["dampeners"]}
    phrases.sort(key=lambda p: -p[0])                  # longest first, so "no complaints at all" is read before "no complaints"
    return Lexicon(d["version"], tuple(e for _, e in phrases), tuple(words), frozenset(negators), frozenset(boosters), frozenset(dampeners))


def _words(chunk: str) -> list[str]:
    return [w.strip(".,;:!?\"()[]") for w in chunk.split()]


def _negated(t: str, start: int, lex: Lexicon) -> bool:
    return any(w in lex.negators for w in _words(t[:start])[-WINDOW:])


def _intensity(t: str, start: int, end: int, arabic: bool, lex: Lexicon) -> float:
    before = _words(t[:start])[-1:]
    after = _words(t[end:])[:1] if arabic else []      # Arabic puts the booster after the word ("ممتاز جدا"); English before it
    near = set(before) | set(after)
    if near & lex.boosters:
        return BOOST
    if near & lex.dampeners:
        return DAMPEN
    return 1.0


def evidence(text: str, lex: Lexicon | None = None) -> tuple[float, float]:
    """(positive, negative) weight found in an already-cleaned text."""
    lex = lex or load()
    t = text
    pos = neg = 0.0
    for e in lex.phrases:
        t, n = e.pattern.subn(" ", t)
        if n:
            if e.positive:
                pos += e.weight * n
            else:
                neg += e.weight * n
    for e in lex.words:
        for m in e.pattern.finditer(t):
            weight = e.weight * _intensity(t, m.start(), m.end(), e.arabic, lex)
            if e.positive != _negated(t, m.start(), lex):      # a negated word reads the other way
                pos += weight
            else:
                neg += weight
    return pos, neg


def verdict(pos: float, neg: float) -> tuple[int, float]:
    """(-1, 0, 1) and a confidence from the evidence. No evidence or a tie is neutral with low confidence; mixed evidence is never confident."""
    if abs(pos - neg) < 1e-9:
        return 0, (0.5 if pos == 0 else 0.55)
    label = 1 if pos > neg else -1
    conf = min(0.95, 0.6 + 0.15 * abs(pos - neg))
    if pos > 0 and neg > 0:
        if abs(pos - neg) < MIXED_GAP:
            return 0, 0.55
        conf = min(conf, 0.7)
    return label, conf
