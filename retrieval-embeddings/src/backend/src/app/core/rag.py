"""Ask your survey (RAG over one open-text question), pure and deterministic. Nothing here calls a model or a database.

Flow: validate the request -> plan retrieval (cosine over stored embeddings of ONE model, floor, cap, minimum evidence) -> the LLM drafts short
sentences that cite retrieved answers -> `verify_answer` accepts the draft or rejects it WHOLE (never repaired). The model never emits SQL, counts,
scores or side effects: a count is only ever produced by code (`count_sentences`) from the structured theme tags and inserted through placeholders."""
import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

import numpy as np

from app.core.normalize_ar import ar_norm
from app.core.query_plan import MIN_N
from app.core.semantic import CrossModelError, assert_same_model, unit
from app.core.text_analysis import informative, script_of

METHOD, PROMPT_VERSION = "rag-1", "rag-1.1"          # 1.1: the prompt spells out the quoting and no-digit rules the verifier enforces (stored answers of 1.0 are asked again)
QUESTION_MIN, QUESTION_MAX = 3, 300
K_DEFAULT, K_MAX = 12, 40
SIM_FLOOR = 0.30            # uncalibrated: depends on the embedding model; calibrate against an analyst-labelled sample (docs/SEMANTIC.md)
MIN_EVIDENCE = MIN_N        # fewer retrieved answers than this -> "not enough data", the LLM is not called (also the min-n for any grouped statement)
POOL_MAX = 5000             # candidate answers scored in Python per question
MAX_SENTENCES, SENT_MIN, SENT_MAX, TOTAL_MAX, MAX_IDS = 5, 12, 300, 900, 8
EVIDENCE_CUT = 400
FALLBACK_QUOTES = 5

STATUSES = ("verified", "insufficient_data", "unverified")


class RagError(ValueError):
    """A request or an input that must be rejected."""


class AnswerRejected(ValueError):
    """The model's draft failed verification; the whole answer is dropped."""


# ---------- request validation ----------
_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f<>]")
_LOCALE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8}){0,2}$")
_LOC = re.compile(r"^[^\x00-\x1f\x7f<>]{1,100}$")
FILTER_KEYS = {"date_from", "date_to", "locale", "location"}


def clean_question(q: str) -> str:
    if not isinstance(q, str):
        raise RagError("question must be text")
    s = re.sub(r"\s+", " ", q).strip()
    if len(s) < QUESTION_MIN:
        raise RagError("question too short")
    if len(s) > QUESTION_MAX:
        raise RagError(f"question longer than {QUESTION_MAX} characters")
    if _CTRL.search(s):
        raise RagError("question contains control characters or markup")
    if not informative(s):
        raise RagError("question has no words")
    return s


def clean_k(k) -> int:
    if k is None:
        return K_DEFAULT
    if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= K_MAX:
        raise RagError(f"k must be an integer between 1 and {K_MAX}")
    return k


@dataclass(frozen=True)
class Filters:
    date_from: date | None = None
    date_to: date | None = None
    locale: str = ""
    location: str = ""

    def as_json(self) -> dict:
        return {"date_from": self.date_from.isoformat() if self.date_from else None, "date_to": self.date_to.isoformat() if self.date_to else None,
                "locale": self.locale, "location": self.location}


def clean_filters(raw: dict | None) -> Filters:
    raw = raw or {}
    if not isinstance(raw, dict):
        raise RagError("filters must be an object")
    if set(raw) - FILTER_KEYS:
        raise RagError("unknown filter")
    d: dict[str, date | None] = {}
    for key in ("date_from", "date_to"):
        v = raw.get(key)
        if v in (None, ""):
            d[key] = None
        elif isinstance(v, date):
            d[key] = v
        elif isinstance(v, str):
            try:
                d[key] = date.fromisoformat(v)
            except ValueError:
                raise RagError(f"{key} must be YYYY-MM-DD") from None
        else:
            raise RagError(f"{key} must be YYYY-MM-DD")
    if d["date_from"] and d["date_to"] and d["date_from"] > d["date_to"]:
        raise RagError("date_from is after date_to")
    loc = raw.get("locale") or ""
    if loc and (not isinstance(loc, str) or not _LOCALE.match(loc)):
        raise RagError("bad locale")
    place = raw.get("location") or ""
    if place and (not isinstance(place, str) or not _LOC.match(place.strip())):
        raise RagError("bad location")
    return Filters(d["date_from"], d["date_to"], loc, place.strip() if place else "")


# ---------- language gate ----------
def unsupported_language(question: str, texts: list[str], supported: frozenset[str] | set[str]) -> str | None:
    """Reason code if the embedder cannot be trusted on this question or on this survey's answers, else None.
    English production only for now: Arabic (or mixed) text with an English-only embedder gives weak retrieval, so we say so instead."""
    if script_of(question) != "en" and "ar" not in supported:
        return "question_language_unsupported"
    if texts:
        ar = sum(1 for t in texts if script_of(t) == "ar")
        if "ar" not in supported and ar * 2 > len(texts):
            return "answer_language_unsupported"
    return None


def supported_text(text: str, supported: frozenset[str] | set[str]) -> bool:
    return "ar" in supported or script_of(text) == "en"


# ---------- redaction of contact data (never sent to the model, never returned) ----------
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<!\w)\+?[\d٠-٩۰-۹][\d٠-٩۰-۹ ().\-]{5,}[\d٠-٩۰-۹]")
_URL = re.compile(r"https?://\S+|www\.\S+", re.I)


def redact(text: str) -> str:
    t = _EMAIL.sub("[contact removed]", text or "")
    t = _URL.sub("[link removed]", t)
    return _PHONE.sub("[contact removed]", t).strip()


def opaque_id(org_id: str, survey_id: str, response_id: str) -> str:
    """Stable id that identifies an answer inside this survey but is not the response id (no join to contact or response records)."""
    return "a_" + hashlib.sha256(f"rag-1|{org_id}|{survey_id}|{response_id}".encode()).hexdigest()[:16]


# ---------- retrieval ----------
@dataclass(frozen=True)
class Candidate:
    id: str
    model_id: str
    dim: int
    vec: tuple[float, ...] | list[float]
    text: str


@dataclass(frozen=True)
class Hit:
    id: str
    score: float
    text: str


@dataclass
class Retrieval:
    status: str                                  # 'ok' | 'insufficient_data'
    reason: str
    hits: list[Hit] = field(default_factory=list)
    considered: int = 0


def plan_retrieval(qvec, q_model: str, q_dim: int, cands: list[Candidate], *, k: int = K_DEFAULT, floor: float = SIM_FLOOR, min_evidence: int = MIN_EVIDENCE) -> Retrieval:
    """Top-k answers by cosine similarity, from ONE embedding model. A candidate from another model/dimension aborts with CrossModelError (never coerced)."""
    clean_k(k)
    if not -1.0 <= floor < 1.0 or min_evidence < MIN_N:
        raise RagError("floor must be in [-1, 1) and the minimum evidence cannot go below the privacy minimum")
    if len(qvec) != q_dim:
        raise CrossModelError(f"query vector has length {len(qvec)}, expected {q_dim}")
    for c in cands:
        assert_same_model(q_model, q_dim, c.model_id, c.dim)
        if len(c.vec) != q_dim:
            raise CrossModelError(f"vector for {c.id} has length {len(c.vec)}, expected {q_dim}")
    pool = [c for c in cands if informative(c.text)]
    if len(pool) > POOL_MAX:
        raise RagError(f"more than {POOL_MAX} candidate answers; narrow the filters")
    if len(pool) < min_evidence:
        return Retrieval("insufficient_data", "too_few_answers", [], len(pool))
    q = unit(qvec)
    m = np.vstack([unit(c.vec) for c in pool])
    sims = m @ q
    order = sorted(range(len(pool)), key=lambda i: (-round(float(sims[i]), 9), pool[i].id))
    passing = [Hit(pool[i].id, round(float(sims[i]), 4), pool[i].text) for i in order if sims[i] >= floor]
    if len(passing) < min_evidence:                         # the minimum counts answers that pass the floor, before k trims what the model sees
        return Retrieval("insufficient_data", "low_similarity", [], len(pool))
    return Retrieval("ok", "", passing[:k], len(pool))


# ---------- counts: only ever computed by code ----------
COUNT_EN = re.compile(r"\b(how many|number of|count of|how much|percent(?:age)?|proportion|share of|ratio|majority|most of)\b|%", re.I)
COUNT_AR = re.compile(r"(كم\b|عدد|نسبة|بالمئة|بالمائة|٪|أغلبية|اغلبية|معظم)")


def is_count_question(q: str) -> bool:
    return bool(COUNT_EN.search(q or "") or COUNT_AR.search(q or ""))


def _words(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w ]", " ", ar_norm(s).lower())).strip()


def match_themes(question: str, themes: list[dict]) -> list[dict]:
    """Frozen themes whose label (any language) or keyword appears as a whole word/phrase in the question."""
    qn = " " + _words(question) + " "
    out = []
    for t in themes:
        names = [*[v for v in (t.get("label") or {}).values() if isinstance(v, str)], *t.get("keywords", []), t["key"].replace("_", " ")]
        for nm in names:
            n = _words(nm)
            if len(n) >= 3 and " " + n + " " in qn:
                out.append(t)
                break
    return out


def fmt_num(v: float) -> str:
    return f"{int(v):,}" if float(v).is_integer() else f"{v:,.1f}"


_PH = re.compile(r"\{\{(ref|label):([a-z0-9_.]+)\}\}")


def _fill(template: str, computed: dict[str, float], labels: dict[str, str]) -> str:
    def sub(m):
        if m.group(1) == "ref":
            if m.group(2) not in computed:
                raise AnswerRejected("unknown ref")
            return fmt_num(computed[m.group(2)])
        if m.group(2) not in labels:
            raise AnswerRejected("unknown label")
        return labels[m.group(2)]
    return _PH.sub(sub, template)


NOTE_COUNTS = "Counts and percentages are not taken from retrieved answers; they come from the structured theme analysis."


def count_sentences(matched: list[dict], counts: dict[str, int], total: int, lang: str = "en") -> tuple[list[dict], dict[str, float]]:
    """Code-written sentences. Returns ({text, template} list, computed). n below the privacy minimum is withheld, never shown."""
    computed: dict[str, float] = {"total": float(total), "min_n": float(MIN_N)}
    labels: dict[str, str] = {}
    out = []
    for t in matched:
        key = t["key"]
        labels[key] = (t.get("label") or {}).get("en") or (t.get("label") or {}).get(lang) or key
        n = counts.get(key, 0)
        if total < MIN_N or n < MIN_N:
            tmpl = "Not shown: fewer than {{ref:min_n}} answers match the theme {{label:" + key + "}}."
        else:
            computed[f"n_{key}"] = float(n)
            tmpl = "The theme {{label:" + key + "}} was tagged on {{ref:n_" + key + "}} of {{ref:total}} answers (keyword tagging, not retrieval)."
        out.append({"text": _fill(tmpl, computed, labels), "template": tmpl})
    return out, computed


# ---------- verifier ----------
_INVIS = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff\u00ad]")
_QUOTE_PAIRS = {'"': '"', "“": "”", "«": "»", "„": "“", "「": "」"}
_QCHARS = set('"“”«»„「」')
_BAD_TEXT = re.compile(r"[<>\x00-\x08\x0b-\x1f\x7f]|https?://|www\.|@", re.I)


def has_digit(s: str) -> bool:
    return any(unicodedata.category(c) in ("Nd", "No", "Nl") for c in _INVIS.sub("", s))


def _wsnorm(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s)).strip().casefold()


def quoted_segments(text: str) -> list[str]:
    """Quoted fragments in the text; raises if quote marks are unbalanced or a quote is empty."""
    out, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch in _QCHARS:
            close = _QUOTE_PAIRS.get(ch)
            if close is None:
                raise AnswerRejected("unbalanced quotation marks")
            j = text.find(close, i + 1)
            if j < 0:
                raise AnswerRejected("unbalanced quotation marks")
            seg = text[i + 1:j]
            if not seg.strip():
                raise AnswerRejected("empty quotation")
            if any(c in _QCHARS for c in seg):
                raise AnswerRejected("nested quotation marks")
            out.append(seg)
            i = j + 1
        else:
            i += 1
    return out


@dataclass(frozen=True)
class VerifiedSentence:
    text: str
    evidence_ids: tuple[str, ...]


def verify_answer(raw, retrieved: dict[str, str], computed: dict[str, float] | None = None, labels: dict[str, str] | None = None) -> list[VerifiedSentence]:
    """`raw`: the model's list of {text, evidence_ids}. `retrieved`: id -> answer text actually shown to the model. Accept all sentences or raise AnswerRejected.
    (a) every id was retrieved, (b) >= 1 id, (c) no digit except through {{ref:..}} placeholders filled here, (d) quotation marks only around text that is
    verbatim in a cited answer, (e) length bounds. Nothing is repaired."""
    computed, labels = computed or {}, labels or {}
    if not isinstance(raw, list):
        raise AnswerRejected("draft is not a list")
    if not 1 <= len(raw) <= MAX_SENTENCES:
        raise AnswerRejected("wrong number of sentences")
    out: list[VerifiedSentence] = []
    total = 0
    for s in raw:
        if not isinstance(s, dict) or set(s) != {"text", "evidence_ids"}:
            raise AnswerRejected("bad sentence shape")
        text, ids = s["text"], s["evidence_ids"]
        if not isinstance(text, str) or not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            raise AnswerRejected("bad sentence types")
        text = text.strip()
        if not SENT_MIN <= len(text) <= SENT_MAX:
            raise AnswerRejected("sentence length out of bounds")
        if not ids:
            raise AnswerRejected("sentence cites no evidence")
        if len(ids) > MAX_IDS or len(set(ids)) != len(ids):
            raise AnswerRejected("too many or repeated evidence ids")
        if any(i not in retrieved for i in ids):
            raise AnswerRejected("evidence id outside the retrieved set")
        if _BAD_TEXT.search(text):
            raise AnswerRejected("markup, link or contact data in sentence")
        phs = _PH.findall(text)
        if any(kind == "ref" and name not in computed for kind, name in phs) or any(kind == "label" and name not in labels for kind, name in phs):
            raise AnswerRejected("unknown placeholder")
        bare = _PH.sub(" ", text)
        if has_digit(bare):
            raise AnswerRejected("digit outside placeholder")
        if "{{" in bare or "}}" in bare:
            raise AnswerRejected("malformed placeholder")
        cited = [_wsnorm(retrieved[i]) for i in ids]
        for seg in quoted_segments(bare):
            if not any(_wsnorm(seg) in c for c in cited):
                raise AnswerRejected("quotation not verbatim in cited answers")
        total += len(text)
        out.append(VerifiedSentence(_fill(text, computed, labels), tuple(ids)))
    if total > TOTAL_MAX:
        raise AnswerRejected("answer too long")
    return out


# ---------- idempotency ----------
def inputs_hash(parts: list) -> str:
    import json
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
