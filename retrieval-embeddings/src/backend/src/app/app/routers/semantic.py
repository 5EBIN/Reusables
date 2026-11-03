"""Semantic analysis (APPEND-ONLY): embeddings, clusters named by a verified LLM, nearest-theme assignment, semantic search.
The model only names clusters; sizes/distances/scores/bands are computed here. Keyword tagging is untouched: semantic assignments are an extra `method`."""
import logging
import hashlib
import json
import uuid
from collections import Counter

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.app.ai_guard import gate, metered
from app.adapters.llm_tasks import served_model
from app.app.deps import OrgCtx, org_ctx
from app.app.routers.surveys import WRITERS
from app.app.routers.text import _texts, _themes
from app.core import semantic as sem
from app.core.query_plan import MIN_N
from app.core.text_analysis import informative, norm
from app.db.repos import analysis_runs as runs_repo
from app.db.repos import answer_tags as tags_repo
from app.db.repos import semantic_clusters as clusters_repo
from app.db.repos import taxonomies as taxonomies_repo
from app.db.repos import text_embeddings as embeddings_repo
from app.db.repos import theme_assignments as assignments_repo

log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/surveys/{sid}/questions/{question}/semantic", tags=["semantic"])
QNAME = r"^[A-Za-z][A-Za-z0-9_]{0,63}$"
Q = Path(..., pattern=QNAME)
BATCH, EXAMPLES_FOR_LLM, EXAMPLES_SHOWN, TEXT_CUT, MAX_EXAMPLE_MEMBERS = 64, 8, 3, 300, 20


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmbedReq(Strict):
    limit: int = Field(200, ge=1, le=500)


class ClusterReq(Strict):
    k: int | None = Field(None, ge=1, le=50)
    k_max: int = Field(8, ge=2, le=50)
    min_size: int = Field(MIN_N, ge=MIN_N, le=1000)       # never below the privacy minimum


class AssignReq(Strict):
    taxonomy_version: int = Field(..., ge=1)
    high: float = Field(sem.HIGH, gt=0, le=1)
    low: float = Field(sem.LOW, gt=0, lt=1)

    @model_validator(mode="after")
    def _order(self):
        sem.check_thresholds(self.high, self.low)
        return self


def _h(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _ihash(parts: list) -> str:
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _emb(o: OrgCtx):
    return o.request.app.state.container.embedder


async def _guard(c, o, credits: bool) -> None:
    await gate(c, o, credits=credits)                      # the llm switch, plan credits, then the daily token and spend caps


async def _embed_checked(emb, texts: list[str], kind: str) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), BATCH):
        part = texts[i:i + BATCH]
        try:
            out.extend(sem.validate_embeddings(await emb.embed(part, kind), len(part), emb.dim))
        except sem.SemanticError as e:
            raise HTTPException(502, f"embedder: {e}") from None
    return out


async def _current(c, sid, question, emb) -> tuple[dict[str, str], dict[str, list[float]]]:
    """(texts by response id, vectors by response id) for answers whose stored embedding is from THIS model and matches the current text."""
    texts = dict(await _texts(c, sid, question))
    rows = await embeddings_repo.vectors_for(c, question, emb.model_id, emb.dim, [uuid.UUID(k) for k in texts])
    vecs: dict[str, list[float]] = {}
    for r in rows:
        rid = str(r.response_id)
        if rid not in vecs and r.source_hash == _h(texts[rid]):
            vecs[rid] = list(r.v)
    return texts, vecs


@router.post("/embed")
async def embed(sid: uuid.UUID, b: EmbedReq = EmbedReq(), question: str = Q, o: OrgCtx = Depends(org_ctx)):
    emb = _emb(o)
    async with o.tx(WRITERS) as c:
        await _guard(c, o, True)
        texts = dict(await _texts(c, sid, question))
        have = await embeddings_repo.existing_hashes(c, question, emb.model_id, [uuid.UUID(k) for k in texts])
        eligible = [(rid, t) for rid, t in sorted(texts.items()) if informative(t)]
        todo = [(rid, t) for rid, t in eligible if (rid, _h(t)) not in have]
        batch = todo[:b.limit]
        vecs = await _embed_checked(emb, [t for _, t in batch], "document")
        for (rid, t), v in zip(batch, vecs, strict=True):
            await embeddings_repo.insert(c, uuid.UUID(o.org_id), uuid.UUID(rid), question, emb.model_id, emb.dim, _h(t), sem.vec_literal(v))
    return {"embedded": len(batch), "skipped": len(eligible) - len(todo), "remaining": len(todo) - len(batch), "model_id": emb.model_id, "dim": emb.dim}


@router.post("/cluster", status_code=201)
async def run_cluster(sid: uuid.UUID, b: ClusterReq = ClusterReq(), question: str = Q, o: OrgCtx = Depends(org_ctx)):
    emb, llm = _emb(o), o.request.app.state.container.llm
    async with o.tx(WRITERS) as c:
        await _guard(c, o, True)
        texts, vecs = await _current(c, sid, question, emb)
        if len(vecs) < b.min_size:
            raise HTTPException(409, f"need at least {b.min_size} embedded answers; run /semantic/embed first")
        ih = _ihash([str(sid), question, emb.model_id, emb.dim, b.k, b.k_max, b.min_size, sem.SEED, "cluster-1", sorted((r, _h(texts[r])) for r in vecs)])
        done = await clusters_repo.run_for_inputs_hash(c, ih)
        if done:
            return {"run_id": str(done), "cached": True}
        try:
            ids, x = sem.build_matrix([(r, emb.model_id, emb.dim, v) for r, v in vecs.items()], emb.model_id, emb.dim)
            res = sem.cluster(ids, x, b.k, b.k_max, b.min_size)
        except sem.SemanticError as e:
            raise HTTPException(409, str(e)) from None
        by_no: dict[int, list[tuple[float, str]]] = {}
        for rid, no, dist in res.members:
            if no != sem.NOISE:
                by_no.setdefault(no, []).append((dist, rid))
        asks, opaque = sem.opaque_asks(by_no, texts, EXAMPLES_FOR_LLM, TEXT_CUT)
        try:
            async with metered(o.request.app.state.pool, o.org_id) as answered:
                proposals = sem.restore_ids(await llm.propose_cluster_labels(asks), opaque) if asks else []
        except Exception as e:                                  # refusal / bad output / outage: clusters simply stay unlabelled
            log.warning("cluster labelling unavailable: %s", type(e).__name__)
            proposals = []
        shown = {no: {rid for _, rid in m} for no, m in by_no.items()}
        labels, dropped = sem.verify_labels(proposals, shown)
        oid, run = uuid.UUID(o.org_id), uuid.uuid4()
        ins = await clusters_repo.insert_run(c, oid, run, sid, question, emb.model_id, res.k,
                                             json.dumps({"k": b.k, "k_max": b.k_max, "min_size": b.min_size, "seed": sem.SEED, "silhouette": res.silhouette, "labels_dropped": len(dropped)}), ih)
        if ins is None:
            return {"run_id": str(await clusters_repo.run_for_inputs_hash(c, ih)), "cached": True}
        for rid, no, dist in res.members:
            await clusters_repo.insert_member(c, oid, run, uuid.UUID(rid), no, dist)
        model_name = served_model(answered, llm)
        for no, lab in sorted(labels.items()):
            await clusters_repo.insert_label(c, oid, run, no, lab.label, lab.description, [uuid.UUID(i) for i in lab.verbatim_ids], model_name)
    return {"run_id": str(run), "cached": False, "k": res.k, "labelled": len(labels), "labels_dropped": len(dropped), "unclustered": sum(1 for m in res.members if m[1] == sem.NOISE)}


@router.get("/clusters")
async def clusters(sid: uuid.UUID, question: str = Q, o: OrgCtx = Depends(org_ctx)):
    async with o.tx(WRITERS) as c:
        run = await clusters_repo.latest_run(c, sid, question)
        if run is None:
            return {"run": None, "clusters": []}
        texts = dict(await _texts(c, sid, question))
        mem = await clusters_repo.members(c, run.run_id)
        labs = await clusters_repo.labels(c, run.run_id)
    groups: dict[int, list] = {}
    for m in mem:
        groups.setdefault(m.cluster_no, []).append(m)
    out = []
    for no in sorted(n for n in groups if n != sem.NOISE):
        ms = groups[no]
        lab = labs.get(no)
        out.append({"cluster_no": no, "size": len(ms), "label": lab.label if lab else None, "description": lab.description if lab else None, "unlabelled": lab is None,
                    "examples": [{"response_id": str(m.response_id), "text": texts.get(str(m.response_id), "")} for m in ms[:EXAMPLES_SHOWN]]})
    params = run.params if isinstance(run.params, dict) else json.loads(run.params)
    return {"run": {"run_id": str(run.run_id), "model_id": run.model_id, "k": run.k, "created_at": run.created_at.isoformat(), "params": params},
            "clusters": out, "unclustered": len(groups.get(sem.NOISE, []))}


@router.post("/assign", status_code=201)
async def assign(sid: uuid.UUID, b: AssignReq, question: str = Q, o: OrgCtx = Depends(org_ctx)):
    emb = _emb(o)
    async with o.tx(WRITERS) as c:
        await _guard(c, o, False)
        st = await taxonomies_repo.status_of(c, sid, question, b.taxonomy_version)
        if st != "frozen":
            raise HTTPException(409, "only approved and frozen taxonomies can be assigned to")
        ths = [t for t in await _themes(c, sid, question, b.taxonomy_version) if t["status"] == "frozen"]
        texts, vecs = await _current(c, sid, question, emb)
        if not vecs:
            raise HTTPException(409, "no embedded answers; run /semantic/embed first")
        ih = _ihash([str(sid), question, b.taxonomy_version, emb.model_id, emb.dim, b.high, b.low, "assign-1",
                     sorted((t["key"], sorted(t["keywords"]), json.dumps(t["label"], sort_keys=True, ensure_ascii=False)) for t in ths), sorted((r, _h(texts[r])) for r in vecs)])
        done = await runs_repo.id_for_hash(c, "semantic_assign", ih)
        if done:
            return {"run_id": str(done), "cached": True}
        classifier = await taxonomies_repo.active_classifier(c, sid, question, b.taxonomy_version)
        tagged = await tags_repo.ordered_for_responses(c, question, b.taxonomy_version, classifier, [uuid.UUID(r) for r in vecs])
        singles: dict[str, list[list[float]]] = {}
        for r in tagged:                                          # approved examples: answers the frozen keyword tagging put in exactly one theme
            if len(r.themes) == 1 and r.themes[0] != "other":
                singles.setdefault(r.themes[0], []).append(vecs[str(r.response_id)])
        kw_texts = [(t["key"], norm(w)) for t in ths for w in [*t["keywords"], t["label"].get("en", "")] if norm(w)]
        kw_vecs = await _embed_checked(emb, [w for _, w in kw_texts], "document") if kw_texts else []
        cents: dict[str, np.ndarray] = {}
        for t in ths:
            cv = sem.theme_centroid([v for (k, _), v in zip(kw_texts, kw_vecs, strict=True) if k == t["key"]], singles.get(t["key"], [])[:MAX_EXAMPLE_MEMBERS])
            if cv is not None:
                cents[t["key"]] = cv
        if not cents:
            raise HTTPException(409, "no theme has keywords or examples to embed")
        oid, run = uuid.UUID(o.org_id), uuid.uuid4()
        ins = await runs_repo.insert_semantic_assign(c, oid, run, sid, question, b.taxonomy_version, emb.model_id, ih, uuid.UUID(o.user_id),
                                                     json.dumps({"high": b.high, "low": b.low}))
        if ins is None:
            return {"run_id": str(await runs_repo.id_for_hash(c, "semantic_assign", ih)), "cached": True}
        bands: Counter = Counter()
        for rid in sorted(vecs):
            a = sem.assign_nearest(vecs[rid], cents, b.high, b.low)
            bands[a.band] += 1
            await assignments_repo.insert_semantic(c, oid, sid, question, b.taxonomy_version, uuid.UUID(rid), a.theme_key, a.score, a.band, emb.model_id, run)
    return {"run_id": str(run), "cached": False, "assigned": bands["assigned"], "review": bands["review"], "other": bands["other"], "method": "semantic"}


@router.get("/assignments")
async def assignments(sid: uuid.UUID, question: str = Q, taxonomy_version: int | None = Query(None, ge=1), o: OrgCtx = Depends(org_ctx)):
    async with o.tx(WRITERS) as c:
        run = await assignments_repo.latest_run(c, sid, question, taxonomy_version)
        if run is None:
            return {"run": None, "counts": [], "review_queue": [], "method": "semantic"}
        rows = await assignments_repo.for_run(c, run.run_id)
        texts = dict(await _texts(c, sid, question))
        tax = await taxonomies_repo.active_classifier(c, sid, question, run.taxonomy_version)
        kw = {str(r.response_id): list(r.themes) for r in await tags_repo.all_for_version(c, question, run.taxonomy_version, tax)}
    cnt = Counter((r.theme_key, r.band) for r in rows)
    counts = [{"theme": t, "band": b, "n": n if n >= MIN_N else None, "suppressed": n < MIN_N} for (t, b), n in sorted(cnt.items())]
    queue = sorted((r for r in rows if r.band == "review"), key=lambda r: (-r.score, str(r.response_id)))[:100]
    return {"run": {"run_id": str(run.run_id), "taxonomy_version": run.taxonomy_version, "model_id": run.model_id}, "method": "semantic", "counts": counts,
            "review_queue": [{"response_id": str(r.response_id), "text": texts.get(str(r.response_id), ""), "theme_key": r.theme_key, "score": r.score,
                              "keyword_themes": kw.get(str(r.response_id), [])} for r in queue]}


@router.get("/search")
async def search(sid: uuid.UUID, question: str = Q, q: str = Query(..., min_length=2, max_length=200), k: int = Query(5, ge=1, le=20), o: OrgCtx = Depends(org_ctx)):
    emb = _emb(o)
    if len(q.strip()) < 2:
        raise HTTPException(422, "query too short")
    async with o.tx(WRITERS) as c:
        await _guard(c, o, False)
        texts, vecs = await _current(c, sid, question, emb)
        n = len(vecs)
        if n < MIN_N:
            return {"n": n, "results": [], "hidden": f"Not shown: only {n} embedded answers (minimum is {MIN_N})", "model_id": emb.model_id}
        qv = (await _embed_checked(emb, [q.strip()], "query"))[0]
        ids = sorted(vecs)
        rows = await embeddings_repo.nearest(c, sem.vec_literal(qv), question, emb.model_id, emb.dim, [uuid.UUID(i) for i in ids], [_h(texts[i]) for i in ids], k)
    return {"n": n, "model_id": emb.model_id, "results": [{"response_id": str(r.response_id), "score": round(r.score, 4), "text": texts[str(r.response_id)]} for r in rows]}
