"""
user-controlled strings (names, emails, file paths, messages) reach reportlab Paragraph markup and file names.
`esc` makes a value safe inside Paragraph markup (it escapes < > & and the quote characters), `safe_name` makes it safe as part of a file name.
"""
from __future__ import annotations

import re
from xml.sax.saxutils import escape

_QUOTES = {'"': "&quot;", "'": "&#39;"}
_BAD_NAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def esc(value) -> str:
    """Escape one interpolated value for a reportlab Paragraph (and for a table cell given as a Paragraph)."""
    return escape("" if value is None else str(value), _QUOTES)


def safe_name(name, fallback: str = "project", limit: int = 60) -> str:
    """A string usable inside a file name: only letters, digits, dot, underscore and hyphen; no path separators, no leading dot, no traversal."""
    cleaned = _BAD_NAME_CHARS.sub("_", str(name or "")).strip("._-")
    cleaned = re.sub(r"\.{2,}", "_", cleaned)                       # no ".." anywhere, even where no separator survives
    cleaned = re.sub(r"_{2,}", "_", cleaned)[:limit].strip("._-")
    return cleaned or fallback
