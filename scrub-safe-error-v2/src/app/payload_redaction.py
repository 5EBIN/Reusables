"""
Redaction of a payload BEFORE it is stored. Recursive over dicts and lists:
  * the value of any key matching (case-insensitive) pass|secret|token|api[_-]?key|authorization|cookie|session|private[_-]?key|credential|dsn|connection[_-]?string is masked
  * string values that look like a credential are masked wherever they sit: JWT, "Bearer ...", PEM blocks, AWS access key ids, sk-... and ghp_... tokens, and URLs carrying credentials
  * strings over 2 KB are truncated with a reference (length + sha256 of the full text)
A caller holding ONE secret value can reduce it with `redact_value` (first 4 characters and the length).
"""
from __future__ import annotations

import hashlib
import re



def redact_value(secret: str) -> str:
    """First 4 characters and the length of one secret value; enough to recognise it, never enough to use it."""
    return f"{secret[:4]}...[{len(secret)} chars]" if secret else ""

MAX_STRING = 2048
MASK = "[REDACTED]"
# counts of LLM tokens are numbers about usage, not credentials (prompt_tokens, completion_tokens, total_tokens, reasoning_tokens, max_tokens ...)
TOKEN_COUNT_KEY = re.compile(r"^(?:prompt|completion|total|reasoning|input|output|cached|max)_tokens$", re.IGNORECASE)
SENSITIVE_KEY = re.compile(r"pass|secret|token|api[_-]?key|authorization|cookie|session|private[_-]?key|credential|dsn|connection[_-]?string", re.IGNORECASE)

# credential-shaped VALUES (replaced in place, so the rest of the string stays readable)
VALUE_PATTERNS = (
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}\b")),
    ("bearer", re.compile(r"\b[Bb]earer\s+[A-Za-z0-9._~+/=-]{8,}")),
    ("pem", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.DOTALL)),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("sk_token", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36}\b")),
    ("url_credentials", re.compile(r"(?<=://)[^/\s:@]{1,100}:[^/\s@]{1,200}(?=@)")),
)


def redact_string(text: str) -> str:
    for name, pattern in VALUE_PATTERNS:
        text = pattern.sub(f"[REDACTED:{name}]", text)
    if len(text) > MAX_STRING:
        digest = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()
        text = f"{text[:MAX_STRING]}... [truncated: {len(text)} chars, sha256 {digest}]"
    return text


def redact(value, _key: str | None = None):
    """A copy of `value` with secrets masked. Never mutates its input."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if isinstance(key, str) and SENSITIVE_KEY.search(key) and not (TOKEN_COUNT_KEY.match(key) and isinstance(item, (int, float))):
                out[key] = MASK
            else:
                out[key] = redact(item, key if isinstance(key, str) else None)
        return out
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return redact_string(value)
    return value
