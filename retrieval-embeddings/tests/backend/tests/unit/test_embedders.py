import numpy as np
import pytest

from app.adapters.embed_fake import FakeEmbedder
from app.adapters.embed_local_en import MODEL, QUERY_PREFIX, LocalEnEmbedder
from app.app.container import build_container


class FakeModel:
    def __init__(self, dim=384, scale=3.0):
        self.calls, self.dim, self.scale = [], dim, scale

    def encode(self, texts, **kw):
        self.calls.append((list(texts), kw))
        return np.array([[self.scale * (1 + (len(t) + j) % 5) for j in range(self.dim)] for t in texts])


async def test_local_en_batches_normalises_and_prefixes_queries():
    m = FakeModel()
    e = LocalEnEmbedder(model=m, batch_size=2)
    assert (e.model_id, e.dim) == (MODEL, 384)
    out = await e.embed(["a", "bb", "ccc"], "document")
    assert len(out) == 3 and [len(c[0]) for c in m.calls] == [2, 1] and m.calls[0][0] == ["a", "bb"]
    assert all(abs(np.linalg.norm(v) - 1) < 1e-9 for v in out)
    await e.embed(["find"], "query")
    assert m.calls[-1][0] == [QUERY_PREFIX + "find"]
    assert await e.embed([], "document") == []


async def test_local_en_rejects_bad_kind_and_wrong_dim():
    with pytest.raises(ValueError):
        await LocalEnEmbedder(model=FakeModel()).embed(["a"], "other")
    with pytest.raises(ValueError):
        await LocalEnEmbedder(model=FakeModel(dim=10)).embed(["a"])


async def test_fake_embedder_deterministic_unit_synonyms():
    e = FakeEmbedder(synonyms={"terrible": "N", "زفت": "N"})
    a, b, c = await e.embed(["terrible", "زفت", "parking"])
    assert a == b and np.dot(a, c) < 0.5 and abs(np.linalg.norm(c) - 1) < 1e-9
    assert (await e.embed(["parking"]))[0] == c
    assert abs(np.linalg.norm((await e.embed([""]))[0]) - 1) < 1e-9
    with pytest.raises(ValueError):
        await e.embed(["x"], "bogus")


def test_container_selects_embedder():
    assert build_container({}).embedder.model_id.startswith("fake-")
    assert build_container({"EMBEDDINGS_PROVIDER": "fake"}).embedder.dim == 256
    with pytest.raises(ValueError):
        build_container({"EMBEDDINGS_PROVIDER": "nope"})
