"""Semantic layer, pure and deterministic: embeddings maths, clustering, nearest-theme assignment, search, and the verifier for LLM cluster labels.

Nothing here calls a model or a database. The model may only NAME clusters (checked by `verify_label`); every size, distance, score and
band comes from this module. Vectors from different embedding models are never compared (`CrossModelError`)."""
import math
import re
import unicodedata
from dataclasses import dataclass

import numpy as np

HIGH, LOW = 0.70, 0.50           # defaults for a bge-class model; calibrate per tenant against analyst labels (docs/SEMANTIC.md)
OTHER = "other"
NOISE = -1                        # members of clusters below min size: never forced into a cluster
LABEL_MAX, DESC_MAX, VERBATIM_MAX = 60, 300, 5
MAX_CLUSTER_N = 3000
SEED = 7
_DIGITS = re.compile(r"[0-9٠-٩۰-۹]")
_BAD = re.compile(r"[<>\x00-\x1f\x7f]")
_WS = re.compile(r"\s+")


class CrossModelError(ValueError):
    """Embeddings from different models (or dimensions) were about to be compared."""


class SemanticError(ValueError):
    pass


def assert_same_model(a_model: str, a_dim: int, b_model: str, b_dim: int) -> None:
    if a_model != b_model or a_dim != b_dim:
        raise CrossModelError(f"cannot compare {a_model}/{a_dim} with {b_model}/{b_dim}")


def unit(v) -> np.ndarray:
    a = np.asarray(v, dtype=np.float64)
    n = float(np.linalg.norm(a))
    if not math.isfinite(n):
        raise SemanticError("non-finite vector")
    return a / n if n > 0 else a


def cosine_checked(a_model: str, a, b_model: str, b) -> float:
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    assert_same_model(a_model, a.shape[0], b_model, b.shape[0])
    return float(np.dot(unit(a), unit(b)))


def build_matrix(rows: list[tuple[str, str, int, list[float]]], model_id: str, dim: int) -> tuple[list[str], np.ndarray]:
    """rows: (id, model_id, dim, vec). Sorted by id; any row from another model or with a wrong length is rejected, never coerced."""
    rows = sorted(rows, key=lambda r: r[0])
    for rid, m, d, v in rows:
        assert_same_model(model_id, dim, m, d)
        if len(v) != dim:
            raise CrossModelError(f"vector for {rid} has length {len(v)}, expected {dim}")
    if not rows:
        return [], np.zeros((0, dim))
    return [r[0] for r in rows], np.vstack([unit(r[3]) for r in rows])


def validate_embeddings(vecs, n: int, dim: int) -> list[list[float]]:
    if not isinstance(vecs, list) or len(vecs) != n:
        raise SemanticError("embedder returned the wrong number of vectors")
    for v in vecs:
        if len(v) != dim or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in v):
            raise SemanticError("embedder returned a malformed vector")
    return [[float(x) for x in v] for v in vecs]


def vec_literal(v) -> str:
    """pgvector text form, e.g. '[0.1,0.2]' (cast with ::vector in SQL)."""
    return "[" + ",".join(repr(float(x)) for x in v) + "]"


# ---------- clustering ----------
@dataclass
class ClusterResult:
    k: int
    members: list[tuple[str, int, float]]      # (id, cluster_no or NOISE, cosine distance to the cluster centroid)
    centroids: dict[int, list[float]]
    silhouette: float | None


def _kmeans(x: np.ndarray, k: int, seed: int, restarts: int = 10) -> np.ndarray:
    """Best of `restarts` seeded runs (highest total cosine to centroid; ties -> first), so the result does not hinge on one unlucky initialisation."""
    best = None
    for r in range(restarts):
        lab, score = _kmeans_once(x, k, seed + r)
        if best is None or score > best[1] + 1e-12:
            best = (lab, score)
    return best[0]


def _kmeans_once(x: np.ndarray, k: int, seed: int, iters: int = 60) -> tuple[np.ndarray, float]:
    n = x.shape[0]
    rng = np.random.default_rng(seed)
    idx = [int(rng.integers(n))]
    for _ in range(1, k):                                      # k-means++ on cosine distance
        d = np.clip(1.0 - np.max(x @ x[idx].T, axis=1), 0, None)
        s = d.sum()
        idx.append(int(np.argmax(d)) if s <= 0 else int(rng.choice(n, p=d / s)))
    cen = x[idx].copy()
    lab = np.full(n, -1)
    for _ in range(iters):
        new = np.argmax(x @ cen.T, axis=1)
        if np.array_equal(new, lab):
            break
        lab = new
        for j in range(k):
            m = x[lab == j]
            if len(m):
                cen[j] = unit(m.mean(axis=0))
            else:                                              # empty cluster: re-seed on the point farthest from its centroid
                cen[j] = x[int(np.argmin(np.max(x @ cen.T, axis=1)))]
    return lab, float(np.sum(np.max(x @ cen.T, axis=1)))


def silhouette(x: np.ndarray, lab: np.ndarray) -> float:
    d = np.clip(1.0 - x @ x.T, 0, None)
    n, ks = len(lab), sorted(set(lab.tolist()))
    if len(ks) < 2:
        return 0.0
    s = np.zeros(n)
    for i in range(n):
        own = lab == lab[i]
        if own.sum() <= 1:
            continue
        a = d[i, own].sum() / (own.sum() - 1)
        b = min(d[i, lab == j].mean() for j in ks if j != lab[i])
        s[i] = (b - a) / max(a, b) if max(a, b) > 0 else 0.0
    return float(s.mean())


def cluster(ids: list[str], x: np.ndarray, k: int | None = None, k_max: int = 8, min_size: int = 5, seed: int = SEED) -> ClusterResult:
    """Seeded spherical k-means. k=None picks k in 2..k_max by best silhouette (ties -> smaller k). Clusters below min_size become NOISE.
    Same ids + same vectors + same params always give the same result; cluster numbers are ordered by size then smallest member id."""
    if len(ids) != x.shape[0] or len(set(ids)) != len(ids):
        raise SemanticError("ids must be unique and match the matrix")
    if min_size < 2 or k_max < 2 or k_max > 50 or (k is not None and not 1 <= k <= 50):
        raise SemanticError("bad clustering parameters")
    order = sorted(range(len(ids)), key=lambda i: ids[i])
    ids, x = [ids[i] for i in order], x[order]
    n = len(ids)
    if n > MAX_CLUSTER_N:
        raise SemanticError("too many answers to cluster at once")
    if n < min_size:
        raise SemanticError("not enough answers")
    sil = None
    lab = np.zeros(n, dtype=int)
    if k is None:
        hi = min(k_max, n // min_size)
        if hi >= 2:
            best = None
            for kk in range(2, hi + 1):
                lab_k = _kmeans(x, kk, seed)
                s = silhouette(x, lab_k)
                if best is None or s > best[0] + 1e-12:
                    best = (s, kk, lab_k)
            sil, _, lab = best
    elif k > 1:
        lab = _kmeans(x, min(k, n), seed)
        sil = silhouette(x, lab)
    keep = [j for j in sorted(set(lab.tolist())) if (lab == j).sum() >= min_size]
    keep.sort(key=lambda j: (-int((lab == j).sum()), min(ids[i] for i in range(n) if lab[i] == j)))
    num = {j: no for no, j in enumerate(keep)}
    cens = {no: unit(x[lab == j].mean(axis=0)) for j, no in num.items()}
    members = []
    for i in range(n):
        if lab[i] in num:
            no = num[lab[i]]
            members.append((ids[i], no, round(max(0.0, 1.0 - float(x[i] @ cens[no])), 6)))
        else:
            members.append((ids[i], NOISE, 0.0))
    return ClusterResult(len(keep), members, {no: [float(v) for v in c] for no, c in cens.items()}, None if sil is None else round(sil, 6))


# ---------- theme assignment ----------
def theme_centroid(keyword_vecs: list, example_vecs: list, example_weight: float = 1.0) -> np.ndarray | None:
    """Centroid of a theme = mean of its keyword embeddings and approved example members (unit vectors), re-normalised."""
    parts = [unit(v) for v in keyword_vecs] + [unit(v) * example_weight for v in example_vecs]
    if not parts:
        return None
    c = np.mean(parts, axis=0)
    return unit(c) if np.linalg.norm(c) > 0 else None


@dataclass(frozen=True)
class Assignment:
    theme_key: str
    score: float
    band: str          # assigned | review | other


def check_thresholds(high: float, low: float) -> None:
    if not (0.0 < low < high <= 1.0):
        raise SemanticError("thresholds need 0 < low < high <= 1")


def assign_nearest(vec, centroids: dict[str, np.ndarray], high: float = HIGH, low: float = LOW) -> Assignment:
    """Nearest approved theme by cosine. >= high -> assigned; [low, high) -> review (human decides); below low -> other. Never forced."""
    check_thresholds(high, low)
    if not centroids:
        return Assignment(OTHER, 0.0, "other")
    v = unit(vec)
    best_k, best = None, -2.0
    for k in sorted(centroids):
        s = float(v @ unit(centroids[k]))
        if s > best + 1e-12:
            best_k, best = k, s
    best = round(best, 6)
    if best >= high:
        return Assignment(best_k, best, "assigned")
    if best >= low:
        return Assignment(best_k, best, "review")
    return Assignment(OTHER, best, "other")


def top_k(query, ids: list[str], x: np.ndarray, k: int = 5, min_score: float = 0.0) -> list[tuple[str, float]]:
    """Pure-Python reference for nearest-neighbour search (the endpoint uses pgvector `<=>`; this is the deterministic oracle)."""
    if x.shape[0] == 0:
        return []
    q = unit(query)
    if q.shape[0] != x.shape[1]:
        raise CrossModelError("query dimension differs from stored embeddings")
    s = x @ q
    order = sorted(range(len(ids)), key=lambda i: (-round(float(s[i]), 9), ids[i]))
    return [(ids[i], round(float(s[i]), 6)) for i in order[:k] if s[i] >= min_score]


# ---------- label verifier ----------
@dataclass(frozen=True)
class ClusterLabel:
    cluster_no: int
    label: str
    description: str
    verbatim_ids: tuple[str, ...]


class LabelRejected(ValueError):
    pass


def _clean(s, field: str, mx: int) -> str:
    if not isinstance(s, str):
        raise LabelRejected(f"{field} must be text")
    s = _WS.sub(" ", unicodedata.normalize("NFC", s)).strip()
    if not s or len(s) > mx:
        raise LabelRejected(f"{field} must be 1-{mx} characters")
    if _DIGITS.search(s):
        raise LabelRejected(f"{field} must not contain numbers (the model never counts)")
    if _BAD.search(s):
        raise LabelRejected(f"{field} contains markup or control characters")
    return s


def verify_label(p, members: dict[int, set[str]]) -> ClusterLabel:
    """label <= 60 chars, description <= 300, no digits/markup, and every verbatim id must be a real member of THAT cluster (quote check)."""
    if not isinstance(p, dict):
        raise LabelRejected("proposal must be an object")
    no = p.get("cluster_no")
    if isinstance(no, bool) or not isinstance(no, int) or no not in members:
        raise LabelRejected("unknown cluster")
    label, desc = _clean(p.get("label"), "label", LABEL_MAX), _clean(p.get("description"), "description", DESC_MAX)
    ids = p.get("verbatim_ids")
    if not isinstance(ids, list) or not 1 <= len(ids) <= VERBATIM_MAX:
        raise LabelRejected(f"verbatim_ids needs 1-{VERBATIM_MAX} entries")
    if any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
        raise LabelRejected("verbatim_ids must be distinct strings")
    if any(i not in members[no] for i in ids):
        raise LabelRejected("verbatim id is not a member of the cluster")
    return ClusterLabel(no, label, desc, tuple(ids))


def opaque_asks(by_no: dict[int, list[tuple[float, str]]], texts: dict[str, str], per_cluster: int, cut: int) -> tuple[list[dict], dict[str, str]]:
    """What the model is shown for labelling: per cluster, the examples nearest the centre as {id, text}, where id is `c<cluster>_<n>`, never a response id
    (a database id has no business in a prompt). Also returns the map from those opaque ids back to the response ids."""
    asks, back = [], {}
    for no, m in sorted(by_no.items()):
        ex = []
        for n, (_, rid) in enumerate(sorted(m)[:per_cluster]):
            back[f"c{no}_{n}"] = rid
            ex.append({"id": f"c{no}_{n}", "text": texts[rid][:cut]})
        asks.append({"cluster_no": no, "examples": ex})
    return asks, back


def restore_ids(proposals, back: dict[str, str]):
    """Opaque ids in the model's `verbatim_ids` back to response ids. An id the model made up stays as it is and fails verification (not a member of the cluster)."""
    if not isinstance(proposals, list):
        return proposals
    return [{**p, "verbatim_ids": [back.get(i, i) if isinstance(i, str) else i for i in p["verbatim_ids"]]} if isinstance(p, dict) and isinstance(p.get("verbatim_ids"), list) else p for p in proposals]


def verify_labels(proposals, members: dict[int, set[str]]) -> tuple[dict[int, ClusterLabel], list[str]]:
    """Valid labels by cluster; everything else is dropped (cluster stays 'unlabelled'). Returns (labels, reasons for drops)."""
    ok: dict[int, ClusterLabel] = {}
    dropped: list[str] = []
    if not isinstance(proposals, list):
        return ok, ["proposals must be a list"]
    for p in proposals:
        try:
            lab = verify_label(p, members)
        except LabelRejected as e:
            dropped.append(str(e))
            continue
        if lab.cluster_no in ok:
            dropped.append("duplicate proposal for cluster")
            continue
        ok[lab.cluster_no] = lab
    return ok, dropped
