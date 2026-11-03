"""Sentiment of one open-text question: run it (model first, word list as the fallback) and read the summary.

The model labels each answer positive, neutral or negative with a confidence; code checks the output (core/sentiment.py). If the model refuses, answers badly
or is unreachable, that batch is labelled by the word list instead and the response says how many batches fell back. The summary applies the organisation's
minimum group size, so a handful of answers is never broken down."""
import logging
import re
import uuid
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.app.ai_guard import check_caps, metered
from app.adapters.llm_tasks import served_model
from app.app.audit import audit
from app.app.deps import OrgCtx, org_ctx
from app.app.routers.semantic import _guard
from app.app.routers.surveys import WRITERS
from app.core.sentiment import MAX_BATCH, SentimentError, from_lexicon, from_model, summarize
from app.db.repos import answer_sentiment as repo
from app.db.repos import answers as answers_repo
from app.db.repos import org_settings

log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/surveys/{sid}/questions/{q}/sentiment", tags=["sentiment"])
QNAME = r"^[A-Za-z][A-Za-z0-9_]{0,63}$"
MAX_PER_RUN = 500
DEFAULT_MIN_GROUP = 5


class Run(BaseModel):
    force: bool = False          # re-label answers that already have a label (for example after changing the model)


def _check(q: str) -> None:
    if not re.match(QNAME, q):
        raise HTTPException(422, "bad question")


async def _ask(llm, texts: list[str]):
    """Asks the model; if the answer fails the checks, asks once more with the reason. A refusal or an outage is not retried: asking again would not change it."""
    try:
        return from_model(texts, await llm.classify_sentiment(texts))
    except SentimentError as e:
        return from_model(texts, await llm.classify_sentiment(texts, hint=str(e)))


@router.post("/run")
async def run(sid: uuid.UUID, q: str, b: Run = Run(), o: OrgCtx = Depends(org_ctx)):
    _check(q)
    cont = o.request.app.state.container
    llm = cont.llm
    model = getattr(llm, "model", type(llm).__name__)          # replaced by the model the provider reports once a batch has been answered
    if not await cont.ask_limiter.hit(f"sentiment:{o.user_id}"):        # each run can cost model requests: same per-user limit as "Ask your survey"
        raise HTTPException(429, "too many runs; wait a minute")
    async with o.tx(WRITERS) as c:
        await _guard(c, o, True)                                           # the organisation may have switched the model provider off; credits are checked too
        texts = [(t.response_id, t.value_text) for t in await answers_repo.texts_for_question(c, sid, q, "", None, None)]
        if not texts:
            raise HTTPException(409, "no text answers")
        done = set() if b.force else await repo.scored_ids(c, q, [rid for rid, _ in texts])
        todo = [(rid, t) for rid, t in texts if rid not in done]
        batch_all, remaining = todo[:MAX_PER_RUN], max(0, len(todo) - MAX_PER_RUN)
        fallback_batches = labelled = 0
        stopped = None
        for i in range(0, len(batch_all), MAX_BATCH):
            if i:
                try:
                    await check_caps(c)                         # the previous batch's real usage may have reached a daily limit: stop cleanly, keep what is labelled
                except HTTPException as e:
                    stopped, remaining = "cap", remaining + len(batch_all) - i
                    log.warning("sentiment run stopped at the daily AI cap after %d answers: %s", labelled, e.detail)
                    break
            batch = batch_all[i:i + MAX_BATCH]
            batch_texts = [t for _, t in batch]
            try:
                async with metered(o.request.app.state.pool, o.org_id) as answered:
                    scored = await _ask(llm, batch_texts)
                used = model = served_model(answered, llm)
            except Exception as e:                              # refusal / bad output / outage (SentimentError included): the word list labels this batch
                log.warning("sentiment model unusable, word list used for %d answers: %s", len(batch), type(e).__name__)       # type only: never the respondents' text
                scored, used = from_lexicon(batch_texts), "lexicon-1"
                fallback_batches += 1
            await repo.upsert_many(c, uuid.UUID(o.org_id), q, used, [(rid, s.label, s.confidence, s.source) for (rid, _), s in zip(batch, scored, strict=True)])
            labelled += len(batch)
        await audit(c, o, "sentiment.run", f"{sid}:{q}", {"labelled": labelled, "fallback_batches": fallback_batches})
    return {"labelled": labelled, "already_labelled": len(done), "remaining": remaining, "fallback_batches": fallback_batches, "model": model, "stopped": stopped}


@router.get("")
async def read(sid: uuid.UUID, q: str, start: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"), end: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
               lang: str = Query("", pattern=r"^(|en|ar|ur|hi|ru|fil)$"), o: OrgCtx = Depends(org_ctx)):
    """Overall summary plus a split by answer language. Answers not yet labelled are counted in `unlabelled`."""
    _check(q)
    if bool(start) != bool(end):
        raise HTTPException(422, "give both start and end, or neither")
    try:
        s_date = date.fromisoformat(start) if start else None
        e_date = date.fromisoformat(end) if end else None
    except ValueError:
        raise HTTPException(422, "bad date") from None
    if s_date and e_date and s_date > e_date:
        raise HTTPException(422, "start is after end")
    async with o.tx() as c:
        texts = await answers_repo.texts_for_question(c, sid, q, lang, s_date, e_date)
        ids = [t.response_id for t in texts]
        stored = await repo.for_answers(c, sid, q, ids)
        models = await repo.models_used(c, sid, q)
        st = await org_settings.get(c)
    min_group = int(getattr(st, "min_group_size", DEFAULT_MIN_GROUP)) if st else DEFAULT_MIN_GROUP
    by_lang = defaultdict(list)
    for r in stored:
        by_lang[r.locale].append((r.label, r.confidence))
    groups = {k: summarize(v, min_group) for k, v in sorted(by_lang.items())}
    if any(g["suppressed"] for g in groups.values()):
        # one small group hidden next to an overall total would let a reader subtract the other groups to recover it: show no split at all
        groups = {"suppressed": True, "note": f"A language has fewer than {min_group} answers: the split is hidden."}
    return {"overall": summarize([(r.label, r.confidence) for r in stored], min_group),
            "by_language": groups,
            "answers": len(texts), "unlabelled": len(texts) - len(stored), "models": models,
            "fallback_used": any(r.source == "lexicon" for r in stored)}
