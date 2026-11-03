"""Narrative verifier: numbers only via {{ref:id}}; directional/causal words only via code-rendered claims."""
import re
import unicodedata
from dataclasses import dataclass, field

REF = re.compile(r"\{\{ref:([a-z0-9_.]+)\}\}")
NUMWORDS_EN = (r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
               r"sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|"
               r"thousand|million|half|third|quarter|double|triple|majority|minority|most|few|first|second|third|"
               r"fourth|fifth|\d+(st|nd|rd|th))\b")
NUMWORDS_AR = (r"(صفر|واحد|اثنان|اثنين|ثلاثة|أربعة|خمسة|ستة|سبعة|ثمانية|تسعة|عشرة|عشرين|ثلاثين|أربعين|خمسين|"
               r"مئة|مائة|ألف|نصف|ثلث|ربع|أغلبية|معظم|أول|ثاني|ثالث)")
DIRECTIONAL = (r"\b(improv\w*|declin\w*|ros[e]|rise[sn]?|fell|fall\w*|increas\w*|decreas\w*|dropp?\w*|grew|grow\w*|"
               r"caus\w*|due to|because|above|below|higher|lower|better|worse|benchmark|industry|average|"
               r"gain\w*|los[ts]\w*)\b")
DIRECTIONAL_AR = r"(أفضل|أسوأ|انخفض\w*|ارتفع\w*|تحسن\w*|تراجع\w*|زاد\w*|بسبب|نتيجة|المعيار|متوسط|فوق|تحت|أعلى|أقل)"
ROMAN = re.compile(r"\b(?=[IVXLCDM]+\b)M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})\b")
INVISIBLE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")


@dataclass
class Claim:
    metric_ref: str
    direction: str  # up|down|flat
    comparison_ref: str | None = None


@dataclass
class Sentence:
    template: str
    refs: list[str] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)


def _has_number_char(s: str) -> bool:
    return any(unicodedata.category(c) in ("Nd", "No") for c in s)


def verify(text: str, computed: dict[str, float], allow_directional_ref: set[str] | None = None):
    """Free-text check. Returns (ok, reason)."""
    refs = REF.findall(text)
    if any(r not in computed for r in refs):
        return False, "unknown ref"
    stripped = REF.sub(" ", text)
    if INVISIBLE.search(stripped):
        stripped = INVISIBLE.sub("", stripped)
        if _has_number_char(stripped):
            return False, "obfuscated digits"
    if _has_number_char(stripped):
        return False, "digit outside placeholder"
    if re.search(NUMWORDS_EN, stripped, re.IGNORECASE) or re.search(NUMWORDS_AR, stripped):
        return False, "number word"
    if ROMAN.search(stripped):
        return False, "roman numeral"
    if re.search(DIRECTIONAL, stripped, re.IGNORECASE) or re.search(DIRECTIONAL_AR, stripped):
        return False, "directional/causal/comparative word in free text"
    if "{{" in stripped or "}}" in stripped:
        return False, "malformed placeholder"
    return True, "ok"


_WORDS = {"up": "increased", "down": "decreased", "flat": "was unchanged"}
_CMP = {"up": "higher than", "down": "lower than", "flat": "equal to"}


def render_claim(c: Claim, computed: dict[str, float]) -> str:
    """Verify claim direction against computed values; render words from code."""
    if c.metric_ref not in computed:
        raise ValueError("unknown ref")
    v = computed[c.metric_ref]
    if c.comparison_ref is not None:
        if c.comparison_ref not in computed:
            raise ValueError("unknown ref")
        v = v - computed[c.comparison_ref]
    actual = "up" if v > 0 else "down" if v < 0 else "flat"
    if actual != c.direction:
        raise ValueError(f"claim direction {c.direction} contradicts computed {actual}")
    if c.comparison_ref is not None:
        return f"{{{{ref:{c.metric_ref}}}}} was {_CMP[c.direction]} {{{{ref:{c.comparison_ref}}}}}"
    return f"{{{{ref:{c.metric_ref}}}}} {_WORDS[c.direction]}"


def verify_sentence(s: Sentence, computed: dict[str, float]) -> str:
    ok, why = verify(s.template, computed)
    if not ok:
        raise ValueError(why)
    parts = [REF.sub(lambda m: f"{{{{ref:{m.group(1)}}}}}", s.template)]
    parts += [render_claim(c, computed) for c in s.claims]
    return " ".join(parts)
