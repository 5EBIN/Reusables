"""Production English embedder: sentence-transformers BAAI/bge-small-en-v1.5 (384-d), run locally (respondent text never leaves the host).
The `semantic` extra provides the library; it is imported lazily, so core installs and tests never need it or the weights.
Model card: queries get the retrieval instruction prefix, documents get none. Multilingual models (bge-m3, multilingual-e5-large, 1024-d)
plug in through the same port as another adapter with their own model_id/dim."""
import asyncio
from typing import Any

import numpy as np

MODEL = "BAAI/bge-small-en-v1.5"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class LocalEnEmbedder:
    model_id = MODEL
    dim = 384
    languages = frozenset({"en"})          # English only: Arabic needs a multilingual adapter that passed evaluation

    def __init__(self, model: Any = None, batch_size: int = 32):
        if model is None:
            from sentence_transformers import SentenceTransformer     # optional dependency: pip install 'app[semantic]'
            model = SentenceTransformer(MODEL)
        self.model, self.batch_size = model, batch_size

    def _encode(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            arr = np.asarray(self.model.encode(texts[i:i + self.batch_size], normalize_embeddings=True, show_progress_bar=False), dtype=np.float64)
            if arr.ndim != 2 or arr.shape[1] != self.dim:
                raise ValueError(f"model returned shape {arr.shape}, expected (n, {self.dim})")
            n = np.linalg.norm(arr, axis=1, keepdims=True)
            out.extend((arr / np.where(n == 0, 1.0, n)).tolist())
        return out

    async def embed(self, texts: list[str], kind: str = "document") -> list[list[float]]:
        if kind not in ("document", "query"):
            raise ValueError("kind must be 'document' or 'query'")
        if not texts:
            return []
        prepared = [QUERY_PREFIX + t for t in texts] if kind == "query" else list(texts)
        return await asyncio.to_thread(self._encode, prepared)
