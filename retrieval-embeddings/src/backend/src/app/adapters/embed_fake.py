"""Deterministic stand-in embedder: hashed word + char-trigram features, L2-normalised. No network, no weights.
`synonyms` maps surface words to a shared concept token so tests can make unrelated strings ("terrible", "awful", "زفت", "سيء") land close."""
import hashlib
import re

import numpy as np

from app.core.normalize_ar import ar_norm

_TOK = re.compile(r"\w+", re.UNICODE)


class FakeEmbedder:
    def __init__(self, dim: int = 256, synonyms: dict[str, str] | None = None):
        self.dim = dim
        self.model_id = f"fake-hash-ngram-{dim}-v1"
        self.languages: frozenset[str] = frozenset({"en"})           # production-like: English only; tests widen it to exercise the multilingual path
        self.synonyms: dict[str, str] = {}
        self.calls: list[tuple[str, int]] = []
        for k, v in (synonyms or {}).items():
            self.add_synonym(k, v)

    def add_synonym(self, word: str, concept: str) -> None:
        self.synonyms[ar_norm(word).lower()] = concept

    def _feats(self, text: str) -> list[tuple[str, float]]:
        out = []
        for tok in _TOK.findall(ar_norm(text or "").lower()):
            if tok in self.synonyms:
                out.append(("c:" + self.synonyms[tok], 3.0))      # concept token only: the surface form is replaced
                continue
            out.append(("w:" + tok, 1.0))
            p = f"^{tok}$"
            out.extend(("g:" + p[i:i + 3], 0.5) for i in range(max(1, len(p) - 2)))
        return out

    def _one(self, text: str) -> list[float]:
        v = np.zeros(self.dim)
        for f, w in self._feats(text):
            h = hashlib.sha256(f.encode()).digest()
            v[int.from_bytes(h[:4], "big") % self.dim] += w if h[4] & 1 else -w
        n = np.linalg.norm(v)
        if n == 0:
            v[0], n = 1.0, 1.0
        return (v / n).tolist()

    async def embed(self, texts: list[str], kind: str = "document") -> list[list[float]]:
        if kind not in ("document", "query"):
            raise ValueError("kind must be 'document' or 'query'")
        self.calls.append((kind, len(texts)))
        return [self._one(t) for t in texts]
