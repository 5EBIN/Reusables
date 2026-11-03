import asyncio

import numpy as np
import pytest

from app.adapters.embed_fake import FakeEmbedder
from app.core import semantic as sem

NEG = ["terrible", "awful", "زفت", "سيء"]
POS = ["excellent", "great", "ممتاز", "رائع"]
SYN = {**{w: "NEG" for w in NEG}, **{w: "POS" for w in POS}}


def emb(texts, syn=SYN):
    return np.array(asyncio.run(FakeEmbedder(synonyms=syn).embed(texts)))


def test_cluster_deterministic_and_arabic_groups_with_english():
    texts = [f"{w} جدا" if i % 2 else f"{w} very" for i, w in enumerate(NEG * 3 + POS * 3)]
    ids = [f"{i:03d}" for i in range(len(texts))]
    x = emb(texts)
    a = sem.cluster(ids, x, k=2, min_size=5)
    b = sem.cluster(list(reversed(ids)), x[::-1], k=2, min_size=5)
    assert a.members == b.members and a.k == 2
    no = {i: n for i, n, _ in a.members}
    assert len({no[f"{i:03d}"] for i in range(12)}) == 1 and len({no[f"{i:03d}"] for i in range(12, 24)}) == 1 and no["000"] != no["012"]
    assert sem.cluster(ids, x, min_size=5).k >= 2


def test_small_clusters_become_noise_not_forced():
    texts = ["terrible"] * 6 + ["parking garage"] * 2
    r = sem.cluster([str(i) for i in range(8)], emb(texts), k=2, min_size=5)
    assert r.k == 1 and sum(1 for m in r.members if m[1] == sem.NOISE) == 2


@pytest.mark.parametrize("kw", [{"min_size": 1}, {"k_max": 1}, {"k_max": 51}, {"k": 0}, {"k": 51}, {"min_size": 0}])
def test_cluster_rejects_bad_params(kw):
    with pytest.raises(sem.SemanticError):
        sem.cluster(["a", "b", "c"], emb(["a", "b", "c"]), **kw)


def test_cluster_rejects_dup_ids_and_too_few():
    with pytest.raises(sem.SemanticError):
        sem.cluster(["a", "a"], emb(["x", "y"]))
    with pytest.raises(sem.SemanticError):
        sem.cluster(["a", "b"], emb(["x", "y"]), min_size=5)


def test_assignment_bands_and_never_forced():
    cents = {"neg": sem.unit(emb(["terrible"])[0]), "pos": sem.unit(emb(["excellent"])[0])}
    v = emb(["awful", "parking garage", "terrible excellent"])
    a = sem.assign_nearest(v[0], cents)
    assert (a.theme_key, a.band) == ("neg", "assigned") and a.score >= sem.HIGH
    assert sem.assign_nearest(v[1], cents).band == "other" and sem.assign_nearest(v[1], cents).theme_key == "other"
    assert sem.assign_nearest(v[2], cents, high=0.99, low=0.3).band == "review"
    assert sem.assign_nearest(v[0], {}).band == "other"


@pytest.mark.parametrize("hi,lo", [(0.5, 0.5), (0.4, 0.6), (1.1, 0.5), (0.5, 0), (0.5, -1), (0, 0)])
def test_threshold_validation(hi, lo):
    with pytest.raises(sem.SemanticError):
        sem.assign_nearest(np.ones(3), {"a": np.ones(3)}, hi, lo)


def test_theme_centroid_and_top_k():
    assert sem.theme_centroid([], []) is None
    c = sem.theme_centroid(emb(["terrible"]), emb(["awful"]))
    assert abs(np.linalg.norm(c) - 1) < 1e-9
    x = emb(["terrible", "terrible", "excellent"])
    assert [i for i, _ in sem.top_k(emb(["awful"])[0], ["b", "a", "c"], x, 2)] == ["a", "b"]


def test_cross_model_rejected():
    with pytest.raises(sem.CrossModelError):
        sem.cosine_checked("m1", [1, 0], "m2", [1, 0])
    with pytest.raises(sem.CrossModelError):
        sem.cosine_checked("m1", [1, 0], "m1", [1, 0, 0])
    with pytest.raises(sem.CrossModelError):
        sem.build_matrix([("a", "m1", 2, [1, 0]), ("b", "m2", 2, [0, 1])], "m1", 2)
    with pytest.raises(sem.CrossModelError):
        sem.build_matrix([("a", "m1", 2, [1, 0, 0])], "m1", 2)
    with pytest.raises(sem.CrossModelError):
        sem.top_k(np.ones(3), ["a"], np.ones((1, 2)))
    assert sem.cosine_checked("m", [1, 0], "m", [1, 0]) == pytest.approx(1.0)


@pytest.mark.parametrize("vecs", [[[1.0]], [[float("nan"), 1.0]], [[1.0, 2.0, 3.0], [1.0, 1.0]], "x", [["a", "b"]]])
def test_validate_embeddings_rejects(vecs):
    with pytest.raises(sem.SemanticError):
        sem.validate_embeddings(vecs, 2, 2)


M = {0: {"a", "b", "c"}, 1: {"d"}}
GOOD = {"cluster_no": 0, "label": "Slow service", "description": "People wait too long.", "verbatim_ids": ["a", "b"]}


def test_label_ok_and_arabic_roundtrip():
    assert sem.verify_label(GOOD, M).label == "Slow service"
    ar = sem.verify_label(GOOD | {"label": "بطء الخدمة", "description": "ينتظر الناس طويلاً."}, M)
    assert ar.label == "بطء الخدمة" and ar.description.startswith("ينتظر")


@pytest.mark.parametrize("bad", [
    {"label": "x" * 61}, {"label": ""}, {"label": "   "}, {"label": 5}, {"label": "Top 3 issues"}, {"label": "٣ مشاكل"}, {"label": "<b>bold</b>"}, {"label": "a\nb\x00"},
    {"description": "d" * 301}, {"description": ""}, {"description": "About 40 percent"},
    {"verbatim_ids": []}, {"verbatim_ids": ["zzz"]}, {"verbatim_ids": ["d"]}, {"verbatim_ids": ["a", "a"]}, {"verbatim_ids": [1]}, {"verbatim_ids": "a"},
    {"verbatim_ids": ["a", "b", "c", "a", "b", "c"]}, {"cluster_no": 9}, {"cluster_no": True}, {"cluster_no": "0"}, {"cluster_no": None},
])
def test_label_rejections(bad):
    with pytest.raises(sem.LabelRejected):
        sem.verify_label(GOOD | bad, M)


def test_label_non_object_and_missing_fields():
    for p in ["x", None, [], {"cluster_no": 0}]:
        with pytest.raises(sem.LabelRejected):
            sem.verify_label(p, M)


def test_label_boundaries_ok():
    sem.verify_label(GOOD | {"label": "x" * 60, "description": "d" * 300}, M)


def test_verify_labels_drops_and_keeps():
    ok, dropped = sem.verify_labels([GOOD, GOOD | {"label": "dup"}, GOOD | {"cluster_no": 1, "verbatim_ids": ["a"]}, "junk"], M)
    assert list(ok) == [0] and len(dropped) == 3 and 1 not in ok
    assert sem.verify_labels("nope", M)[0] == {}


def test_opaque_asks_hide_response_ids_and_restore_ids_maps_them_back():
    by_no = {0: [(0.2, "11111111-1111-1111-1111-111111111111"), (0.1, "22222222-2222-2222-2222-222222222222")], 1: [(0.3, "33333333-3333-3333-3333-333333333333")]}
    texts = {r: f"text {i}" for i, r in enumerate(["11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222", "33333333-3333-3333-3333-333333333333"])}
    asks, back = sem.opaque_asks(by_no, texts, per_cluster=2, cut=4)
    assert asks == [{"cluster_no": 0, "examples": [{"id": "c0_0", "text": "text"}, {"id": "c0_1", "text": "text"}]}, {"cluster_no": 1, "examples": [{"id": "c1_0", "text": "text"}]}]
    assert back["c0_0"] == "22222222-2222-2222-2222-222222222222" and back["c1_0"] == "33333333-3333-3333-3333-333333333333"      # nearest first
    props = [{"cluster_no": 0, "label": "l", "description": "d", "verbatim_ids": ["c0_1"]}]
    labels, dropped = sem.verify_labels(sem.restore_ids(props, back), {0: {"11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"}})
    assert labels[0].verbatim_ids == ("11111111-1111-1111-1111-111111111111",) and not dropped


def test_an_invented_or_foreign_opaque_id_fails_verification():
    back = {"c0_0": "a", "c1_0": "b"}
    members = {0: {"a"}, 1: {"b"}}
    for ids in (["c9_9"], ["c1_0"], ["a-real-looking-id"]):                                      # invented, another cluster's, or an id the model was never shown
        labels, dropped = sem.verify_labels(sem.restore_ids([{"cluster_no": 0, "label": "l", "description": "d", "verbatim_ids": ids}], back), members)
        assert not labels and dropped
    assert sem.restore_ids("not a list", back) == "not a list"
