"""Tolerant key matching for a model's tool-choice JSON: a key that is an exact variant of one accepted key is used as that key."""
from __future__ import annotations

import re

_SUBFIELD_WORDS = frozenset({"pattern", "limit", "path", "glob", "type", "mode", "ignore", "case", "context", "offset", "ref"})


def exact_variant(key, known) -> str | None:
    """The one accepted key that `key` is an exact variant of: `<key>_<word>` or `<word>_<key>` (a model that suffixes every key, e.g. `reads_file`), or None. Strict on purpose:
    lower-case words and underscores only; exactly one accepted key may match; the extra word is a single word that is not an item field name (so `reads_path`
    stay rejected); and the key must not be part of another accepted key (`symbol_lookup` is not `symbol`: it is a piece of `needs_symbol_lookup`)."""
    if not isinstance(key, str) or not re.fullmatch(r"[a-z]+(?:_[a-z]+)*", key) or any(key in k for k in known):
        return None
    hits = set()
    for k in known:
        extra = key[len(k) + 1:] if key.startswith(k + "_") else key[:-len(k) - 1] if key.endswith("_" + k) else None
        if extra and "_" not in extra and extra not in _SUBFIELD_WORDS:
            hits.add(k)
    return next(iter(hits)) if len(hits) == 1 else None
