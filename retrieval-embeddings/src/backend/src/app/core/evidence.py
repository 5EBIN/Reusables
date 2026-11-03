"""Evidence checks shared by benchmarks and market research: a number is only allowed if it appears in a stored snippet
(after normalising digits/separators) or is derived by code from numbers that do."""
import hashlib
import re

from app.core.distribution import AR_DIGITS

NUM = re.compile(r"(?<![A-Za-z0-9_.])-?[\d٠-٩۰-۹][\d٠-٩۰-۹,٬]*(?:[.٫][\d٠-٩۰-۹]+)?[%٪]?")


def _norm_num(s: str) -> str:
    s = s.translate(AR_DIGITS).replace("٬", "").replace(",", "").replace("٫", ".").rstrip("%٪")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def numbers_in(text: str) -> set[str]:
    return {_norm_num(m.group(0)) for m in NUM.finditer(text or "")}


def number_supported(value: float | str, snippet: str) -> bool:
    return _norm_num(str(value)) in numbers_in(snippet)


def derived_supported(value: float, snippet_numbers: list[float], tol: float = 0.011) -> bool:
    """True if value equals a sum, difference, product, ratio or percentage change of two supported numbers (code-derived)."""
    for a in snippet_numbers:
        for b in snippet_numbers:
            cands = [a + b, a - b, a * b]
            if b:
                cands += [a / b, (a - b) / b * 100]
            if any(abs(value - c) <= tol * max(1.0, abs(c)) for c in cands):
                return True
    return False


def snippet_hash(snippet: str) -> str:
    return hashlib.sha256(snippet.encode()).hexdigest()
