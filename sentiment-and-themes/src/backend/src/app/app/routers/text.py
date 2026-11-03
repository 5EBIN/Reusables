"""Open-text analysis: taxonomy lifecycle, tagging, theme shares, evidence, verified summary."""
import hashlib
import json
import logging
import uuid
from collections import Counter
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.app.ai_guard import check_caps, gate, metered
from app.app.ai_fallback import narrate_or_none
from app.app.analytics.engine import run_query
from app.app.deps import OrgCtx, org_ctx
from app.app.security import require_sensitive
from app.app.routers.surveys import WRITERS
from app.core.narrative import NarrativeError, parse_sentences, render
from app.core.query_plan import QueryPlan
from app.adapters.llm_tasks import LLMUnavailable, served_model
from app.core.themes import valid_proposals
from app.core.text_analysis import (
    KeywordClassifier, LLMThemeClassifier, Theme, ThemeResult, gate_from_results, informative, script_of, select_quotes, stratified_sample, taxonomy_gate,
)
from app.db.repos import analysis_runs as runs_repo
from app.db.repos import answer_tags as tags_repo
from app.db.repos import answers as answers_repo
from app.db.repos import taxonomies as taxonomies_repo
from app.db.repos import themes as themes_repo

log = logging.getLogger("app.text")
router = APIRouter(prefix="/v1/surveys/{sid}/questions/{q}", tags=["text-analysis"])
QNAME = r"^[A-Za-z][A-Za-z0-9_]{0,63}$"
MAX_SAMPLE = 200


class Decide(BaseModel):
    action: Literal["approve", "reject", "merge"]
    merge_into: uuid.UUID | None = None


class TagRun(BaseModel):
    classifier: Literal["keyword", "llm"] = "keyword"


TAG_BATCH = 50                       # answers per model request
TAG_MAX = 1000                       # answers the model tags in one run (20 requests); the keyword classifier has no limit


async def _texts(c, sid, q, lang="", start=None, end=None):
    rows = await answers_repo.texts_for_question(c, sid, q, lang, start, end)
    return [(str(r.response_id), r.value_text) for r in rows]


async def _themes(c, sid, q, version):
    rows = await themes_repo.for_taxonomy(c, sid, q, version)
    return [t.model_dump() | {"label": json.loads(t.label)} for t in rows]


def _to_theme(t) -> Theme:
    return Theme(t["key"], t["label"], list(t["keywords"]))


@router.post("/taxonomy/propose", status_code=201)
async def propose(sid: uuid.UUID, q: str, o: OrgCtx = Depends(org_ctx)):
    if not __import__("re").match(QNAME, q):
        raise HTTPException(422, "bad question")
    llm = o.request.app.state.container.llm
    async with o.tx(WRITERS) as c:
        await gate(c, o)                                     # respondent text goes to the model provider: the organisation's switch, then the daily caps
        texts = await _texts(c, sid, q)
        if len(texts) < 5:
            raise HTTPException(409, "need at least 5 text answers")
        rows = [{"id": str(r.response_id), "text": r.value_text, "locale": r.locale, "month": r.month, "rating": None if r.rating is None else float(r.rating)}
                for r in await answers_repo.texts_with_context(c, sid, q)]
        sample = [r["text"] for r in stratified_sample(rows, MAX_SAMPLE, f"{sid}|{q}")]
        ih = hashlib.sha256(json.dumps([sorted(sample), "propose-2"], ensure_ascii=False).encode()).hexdigest()
        done = await runs_repo.theme_discovery_version(c, ih)
        if done is not None:
            return {"taxonomy_version": done, "cached": True}
        try:
            async with metered(o.request.app.state.pool, o.org_id) as answered:
                raw = await llm.propose_themes(sample, 12)
        except LLMUnavailable as e:                             # outage, breaker open, credits or key: nothing was proposed, nothing is stored
            log.warning("theme proposal unavailable: %s", type(e).__name__)
            raise HTTPException(409, {"code": "ai_unavailable", "reason": "The assistant could not propose themes right now. Try again in a few minutes, or add themes by hand."}) from None
        except Exception as e:                                  # refusal, or a reply that stays invalid after the re-ask: the same outcome as proposals that all fail validation
            log.warning("theme proposal unusable: %s", type(e).__name__)
            raw = []
        themes = valid_proposals(raw)                           # core/themes.py: the same model that built the schema the model answered to
        if not themes:
            raise HTTPException(409, "no valid theme proposals")
        v = await taxonomies_repo.next_version(c, sid, q)
        oid = uuid.UUID(o.org_id)
        await taxonomies_repo.insert(c, oid, sid, q, v)
        for t in themes:
            await themes_repo.insert(c, oid, uuid.uuid4(), sid, q, v, t["key"], json.dumps({k: x for k, x in t["label"].items() if x}, ensure_ascii=False),
                                     t["definition"], t["keywords"], uuid.UUID(o.user_id))
        await runs_repo.insert_theme_discovery(c, oid, uuid.uuid4(), sid, q, v, ih, uuid.UUID(o.user_id), served_model(answered, llm))
    return {"taxonomy_version": v, "cached": False, "themes": len(themes)}


@router.get("/taxonomy")
async def get_taxonomy(sid: uuid.UUID, q: str, o: OrgCtx = Depends(org_ctx)):
    async with o.tx() as c:
        vers = await taxonomies_repo.versions(c, sid, q)
        texts = await _texts(c, sid, q)
        out = []
        for v in vers:
            ths = await _themes(c, sid, q, v.version)
            clf = KeywordClassifier([_to_theme(t) for t in ths])
            res = clf.classify([t for _, t in texts])
            counts = Counter(k for r in res for k in r.themes)
            example: dict[str, str] = {}
            for (_, txt), r in zip(texts, res, strict=True):          # first verbatim answer (stable order) that matches the theme
                for k in r.themes:
                    example.setdefault(k, txt[:140])
            out.append({"version": v.version, "status": v.status, "multi_label": v.multi_label,
                        "themes": [{"id": str(t["id"]), "key": t["key"], "label": t["label"], "definition": t["definition"], "merged_into": str(t["merged_into"]) if t["merged_into"] else None,
                                    "status": t["status"], "matches": counts.get(t["key"], 0), "example": example.get(t["key"])} for t in ths]})
    return {"versions": out}


@router.post("/taxonomy/{version}/themes/{theme_id}/decide")
async def decide(sid: uuid.UUID, q: str, version: int, theme_id: uuid.UUID, b: Decide, o: OrgCtx = Depends(org_ctx)):
    async with o.tx(WRITERS) as c:
        st = await taxonomies_repo.status_of(c, sid, q, version)
        if st is None:
            raise HTTPException(404, "not found")
        if st != "draft":
            raise HTTPException(409, "taxonomy is frozen; propose a new version")
        t = await themes_repo.status_in_taxonomy(c, theme_id, sid, q, version)
        if t is None:
            raise HTTPException(404, "not found")
        if b.action == "merge":
            tgt = b.merge_into and await themes_repo.exists_in_taxonomy(c, b.merge_into, version, sid, q)
            if not tgt or b.merge_into == theme_id:
                raise HTTPException(422, "merge target invalid")
            kws = await themes_repo.keywords_of(c, theme_id)
            await themes_repo.add_keywords(c, b.merge_into, kws)
            await themes_repo.reject_merged(c, theme_id, b.merge_into, uuid.UUID(o.user_id))
        else:
            await themes_repo.set_status(c, theme_id, "approved" if b.action == "approve" else "rejected", uuid.UUID(o.user_id))
    return {"ok": True}


class Rename(BaseModel):
    label: dict[str, str]


@router.post("/taxonomy/{version}/themes/{theme_id}/rename")
async def rename(sid: uuid.UUID, q: str, version: int, theme_id: uuid.UUID, b: Rename, o: OrgCtx = Depends(org_ctx)):
    if "en" not in b.label or not 1 <= len(b.label) <= 6 or any(not 1 <= len(v.strip()) <= 80 or k not in ("en", "ar", "ur", "hi", "ru", "fil") for k, v in b.label.items()):
        raise HTTPException(422, "label needs a short English name; other languages optional")
    async with o.tx(WRITERS) as c:
        st = await taxonomies_repo.status_of(c, sid, q, version)
        if st is None:
            raise HTTPException(404, "not found")
        if st != "draft":
            raise HTTPException(409, "taxonomy is frozen; propose a new version")
        matched = await themes_repo.rename(c, theme_id, sid, q, version, json.dumps({k: v.strip() for k, v in b.label.items()}, ensure_ascii=False))
    if not matched:
        raise HTTPException(404, "not found")
    return {"ok": True}


@router.post("/taxonomy/{version}/freeze")
async def freeze(sid: uuid.UUID, q: str, version: int, o: OrgCtx = Depends(org_ctx)):
    async with o.tx(WRITERS) as c:
        st = await taxonomies_repo.status_of(c, sid, q, version)
        if st is None:
            raise HTTPException(404, "not found")
        if st == "frozen":
            return {"status": "frozen"}
        if not await themes_repo.approved_count(c, sid, q, version):
            raise HTTPException(409, "approve at least one theme first")
        await themes_repo.freeze_approved(c, sid, q, version)
        await taxonomies_repo.freeze(c, sid, q, version, uuid.UUID(o.user_id))
    return {"status": "frozen"}


async def _model_picks(o, c, llm, texts: list[str], theme_ids: list[str]) -> list[str | None]:
    """The theme id the model picks for each answer that says something (None for the rest), batch by batch. The daily caps are checked again between batches, and any failure
    ends the run here, before anything is written: a taxonomy is never tagged half by the model."""
    todo = [i for i, t in enumerate(texts) if informative(t)]
    if len(todo) > TAG_MAX:
        raise HTTPException(409, {"code": "too_many_answers", "answers": len(todo), "max": TAG_MAX})
    picks: list[str | None] = [None] * len(texts)
    for start in range(0, len(todo), TAG_BATCH):
        if start:
            await check_caps(c)                               # the previous batch's real usage may have reached a daily limit (429)
        part = todo[start:start + TAG_BATCH]
        try:
            async with metered(o.request.app.state.pool, o.org_id):
                got = await llm.classify([texts[i] for i in part], theme_ids)
        except Exception as e:                                # outage, breaker, credits, refusal, or a reply that stays invalid after the re-ask
            log.warning("model tagging unavailable: %s", type(e).__name__)
            raise HTTPException(409, {"code": "ai_unavailable", "reason": "The assistant could not tag the answers right now. Try again in a few minutes, or tag with the keyword classifier."}) from None
        for i, theme in zip(part, got, strict=True):
            picks[i] = theme
    return picks


@router.post("/taxonomy/{version}/tag")
async def tag(sid: uuid.UUID, q: str, version: int, b: TagRun = TagRun(), o: OrgCtx = Depends(org_ctx)):
    llm = o.request.app.state.container.llm
    by_model = b.classifier == "llm"
    async with o.tx(WRITERS) as c:
        st = await taxonomies_repo.status_of(c, sid, q, version)
        if st != "frozen":
            raise HTTPException(409, "only approved and frozen taxonomies can tag")
        ths = [t for t in await _themes(c, sid, q, version) if t["status"] == "frozen"]
        themes = [_to_theme(t) for t in ths]
        texts = await _texts(c, sid, q)

        def enforce(clf) -> None:
            verdict = taxonomy_gate(clf, [t for _, t in texts])
            if verdict["status"] == "fail":
                raise HTTPException(409, {"code": "classifier_gate_failed", "gate": verdict})        # this taxonomy leaves too many of this organisation's answers in "other"
        if by_model:
            await gate(c, o)                                     # respondent text goes to the model provider: the organisation's switch, then the daily caps
            version_tag = f"llm-1:{getattr(llm, 'model', type(llm).__name__)}"
        else:
            clf = KeywordClassifier(themes)
            version_tag = clf.version
            enforce(clf)
        ih = hashlib.sha256(json.dumps([version, version_tag, sorted(texts), [t["key"] for t in ths]], ensure_ascii=False).encode()).hexdigest()
        cached = await runs_repo.tagging_done(c, ih)
        oid = uuid.UUID(o.org_id)
        if not cached:
            if by_model:                                      # a stored run already passed the gate: no new model calls for the same answers, model and themes
                picks = await _model_picks(o, c, llm, [t for _, t in texts], [t["key"] for t in ths])
                clf = LLMThemeClassifier(lambda _: picks, themes, version_tag)
                enforce(clf)
            res = clf.classify([t for _, t in texts])
            for (rid, _), r in zip(texts, res, strict=True):
                await tags_repo.upsert_tag(c, oid, uuid.UUID(rid), q, version, version_tag, r.themes, r.sentiment, r.confidence, r.unclassified)
            await runs_repo.insert_tagging(c, oid, uuid.uuid4(), sid, q, version, version_tag, ih, uuid.UUID(o.user_id), json.dumps({"tagged": len(texts)}))
        await taxonomies_repo.set_active_classifier(c, sid, q, version, version_tag)
    return {"tagged": len(texts), "cached": bool(cached), "classifier_version": version_tag}


@router.get("/analysis")
async def analysis(sid: uuid.UUID, q: str, start: str, end: str, lang: str = Query("", pattern=r"^(|en|ar|ur|hi|ru|fil)$"), o: OrgCtx = Depends(org_ctx)):
    """Everything the text-analysis screen shows: shares (exact), sentiment, language split, evidence, gates, trail. Period and language apply to every part."""
    plan = QueryPlan.model_validate({"metric": "THEME_SHARE", "date_range": {"start": start, "end": end}, "filters": [
        {"dim": "SURVEY", "op": "eq", "value": str(sid)}, {"dim": "QUESTION", "op": "eq", "value": q}] + ([{"dim": "LOCALE", "op": "eq", "value": lang}] if lang else [])})
    async with o.tx() as c:
        shares = await run_query(c, plan)
        texts = dict(await _texts(c, sid, q, lang, plan.date_range.start, plan.date_range.end))
        tax = await taxonomies_repo.latest_frozen_with_approval(c, sid, q)
        sent = {}
        quotes = {}
        gate = None
        if tax:
            frozen = [t for t in await _themes(c, sid, q, tax.version) if t["status"] == "frozen"]
            rows = await tags_repo.for_analysis(c, sid, q, tax.version, tax.active_classifier, [uuid.UUID(k) for k in texts])
            if str(tax.active_classifier or "").startswith("llm-"):          # tagged by the model: the gate measures the tags it made, not what the keyword list would have made
                gate = gate_from_results([ThemeResult(list(r.themes), bool(r.unclassified)) for r in rows])
            else:
                gate = taxonomy_gate(KeywordClassifier([_to_theme(t) for t in frozen]), list(texts.values()))      # this organisation's taxonomy on its own answers
            c_sent = Counter()
            items = []
            for r in rows:
                c_sent["low_confidence" if (r.sentiment_conf or 0) < 0.6 else {1: "positive", 0: "neutral", -1: "negative"}[r.sentiment]] += 1
                items.append((str(r.response_id), texts.get(str(r.response_id), ""), list(r.themes)))
            n = len(rows)
            sent = {"n": n, "counts": dict(c_sent),
                    "positive_pct": round(100 * c_sent["positive"] / n, 1) if n else None,
                    "negative_pct": round(100 * c_sent["negative"] / n, 1) if n else None,
                    "note": "Low-confidence labels (below 0.6) are shown as neutral and flagged."}
            seed = f"{sid}:{q}:{tax.version}"
            themes = {t for _, _, th in items for t in th}
            quotes = {t: select_quotes(items, t, seed, 3) for t in sorted(themes)}
            label_of = {str(r.response_id): "low_confidence" if (r.sentiment_conf or 0) < 0.6 else {1: "positive", 0: "neutral", -1: "negative"}[r.sentiment] for r in rows}
            for lst in quotes.values():
                for qt in lst:
                    qt["sentiment"] = label_of.get(qt["response_id"])
    langs = Counter(script_of(t) for t in texts.values())
    return {"shares": shares, "sentiment": sent, "languages": dict(langs), "taxonomy": tax.model_dump() if tax else None,
            "evidence": quotes, "classifier_gate": gate, "answers": len(texts)}


@router.get("/analysis/export")
async def export_analysis(sid: uuid.UUID, q: str, o: OrgCtx = Depends(org_ctx)):
    """CSV of the tagged open-text answers: one row per answer with its themes and sentiment. Cells are formula-neutralised like every export."""
    if not __import__("re").match(QNAME, q):
        raise HTTPException(422, "bad question")
    from fastapi.responses import Response

    from app.app.audit import audit
    from app.core import exporters as ex
    async with o.tx(WRITERS) as c:
        await require_sensitive(o, "export.respondent_data")          # one row per answer, with its response id and the respondent's own words
        tax = await taxonomies_repo.latest_frozen(c, sid, q)
        if tax is None:
            raise HTTPException(409, "no approved taxonomy to export")
        lab = {t["key"]: str(t["label"].get("en") or next(iter(t["label"].values()), t["key"])) for t in await _themes(c, sid, q, tax.version)}
        rows = await answers_repo.tagged_for_export(c, sid, q, tax.version, tax.active_classifier)
        await audit(c, o, "text.export", f"{sid}:{q}", {"rows": len(rows)})
    sent = {1: "positive", 0: "neutral", -1: "negative"}
    t = ex.Table([ex.Col("response_id", "Response ID", "text"), ex.Col("locale", "Language", "text"), ex.Col("text", "Answer", "text"), ex.Col("themes", "Themes", "text"), ex.Col("sentiment", "Sentiment", "text")],
                 [[str(r.response_id), r.locale, r.value_text, "; ".join(lab.get(k, k) for k in (r.themes or [])) or ("unclassified" if r.unclassified else ""), sent.get(r.sentiment, "") if r.sentiment is not None else ""] for r in rows])
    return Response(ex.to_csv(t), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="text-analysis-{q}.csv"', "Cache-Control": "no-store"})


@router.post("/summary", status_code=201)
async def summary(sid: uuid.UUID, q: str, start: str, end: str, o: OrgCtx = Depends(org_ctx)):
    """Verified narrative. Model drafts; code verifies; on any failure fall back to the code-only summary."""
    llm = o.request.app.state.container.llm
    data = await analysis(sid, q, start, end, "", o)
    shares = data["shares"]
    if shares["outcome"] != "ANSWER":
        raise HTTPException(409, shares.get("reason") or "no tagged data")
    rows = [r for r in shares["rows"] if not r.get("suppressed")]
    computed: dict[str, float] = {"n_total": float(rows[0]["n_total"]) if rows else 0.0}
    labels: dict[str, str] = {}
    for r in rows:
        computed[f"theme.{r['theme']}.n"] = float(r["n"])
        labels[f"theme.{r['theme']}"] = r["theme"]
    s = data["sentiment"]
    if s.get("n"):
        computed["sent.pos_pct"], computed["sent.neg_pct"] = s["positive_pct"], s["negative_pct"]
    async with o.tx(WRITERS) as c0:
        await gate(c0, o)
    drafted = await narrate_or_none(llm, "text_summary", computed, labels, pool=o.request.app.state.pool, org_id=o.org_id)
    source = "model-assisted"
    try:
        if not drafted:
            raise NarrativeError("empty")
        rendered = render(parse_sentences(drafted), computed, labels)
    except NarrativeError:
        top = max((r for r in rows if r["theme"] not in ("other", "unclassified")), key=lambda r: r["n"], default=None)
        sent_ = [{"template": "{{ref:n_total}} open-text answers were analysed."}]
        if top:
            sent_.append({"template": f"{{{{label:theme.{top['theme']}}}}} appears in {{{{ref:theme.{top['theme']}.n}}}} of them."})
        rendered = render(parse_sentences(sent_), computed, labels)
        source = "computed"
    run_id = uuid.uuid4()
    ih = hashlib.sha256(json.dumps([sid.hex, q, sorted(computed.items()), rendered.text], ensure_ascii=False).encode()).hexdigest()
    async with o.tx(WRITERS) as c:
        await runs_repo.insert_summary(c, uuid.UUID(o.org_id), run_id, sid, q, source, ih,
                                       json.dumps({"text": rendered.text, "refs_total": rendered.refs_total, "refs_traced": rendered.refs_traced, "claims": rendered.claims}),
                                       uuid.UUID(o.user_id))
        rid = await runs_repo.summary_id_for_hash(c, ih)
    return {"id": str(rid), "text": rendered.text, "provenance": source, "status": "draft",
            "verification": {"refs_total": rendered.refs_total, "refs_traced": rendered.refs_traced, "claims": rendered.claims}}


@router.get("/summary")
async def latest_summary(sid: uuid.UUID, q: str, o: OrgCtx = Depends(org_ctx)):
    """The most recent verified summary for the question (draft or reviewed), with how it was made."""
    async with o.tx() as c:
        r = await runs_repo.latest_summary(c, sid, q)
    if r is None:
        return {"summary": None}
    out = json.loads(r.output) if isinstance(r.output, str) else r.output
    return {"summary": {"id": str(r.id), "text": out.get("text", ""), "provenance": "model-assisted" if r.model == "model-assisted" else "computed", "status": r.status,
                        "prompt_version": r.prompt_version, "prompt_hash": r.inputs_hash[:8], "created_at": r.created_at.isoformat(),
                        "reviewed_by": r.reviewer, "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
                        "verification": {"refs_total": out.get("refs_total", 0), "refs_traced": out.get("refs_traced", 0), "claims": out.get("claims", 0)}}}


@router.post("/summary/{run_id}/review")
async def review_summary(sid: uuid.UUID, q: str, run_id: uuid.UUID, o: OrgCtx = Depends(org_ctx)):
    async with o.tx(WRITERS) as c:
        matched = await runs_repo.mark_summary_reviewed(c, run_id, uuid.UUID(o.user_id))
    if not matched:
        raise HTTPException(404, "not found")
    return {"status": "reviewed"}
