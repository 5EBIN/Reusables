"""SQL for answer_sentiment (one sentiment label per open-text answer, see migration 0190)."""
import uuid

import asyncpg
from pydantic import BaseModel


class Stored(BaseModel):
    response_id: uuid.UUID
    locale: str
    label: int
    confidence: float
    source: str


async def scored_ids(c: asyncpg.Connection, question_id: str, response_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    """Which of these answers already have a label."""
    rows = await c.fetch("select response_id from answer_sentiment where question_id=$1 and response_id = any($2::uuid[])", question_id, response_ids)
    return {r["response_id"] for r in rows}


async def upsert_many(c: asyncpg.Connection, org_id: uuid.UUID, question_id: str, model: str, rows: list[tuple[uuid.UUID, int, float, str]]) -> None:
    """rows: (response_id, label, confidence, source). A re-run replaces the earlier label."""
    await c.executemany("""insert into answer_sentiment(org_id,response_id,question_id,label,confidence,source,model) values($1,$2,$3,$4,$5,$6,$7)
        on conflict (org_id,response_id,question_id) do update set label=excluded.label, confidence=excluded.confidence, source=excluded.source,
            model=excluded.model, created_at=now()""", [(org_id, rid, question_id, label, conf, source, model) for rid, label, conf, source in rows])


async def for_answers(c: asyncpg.Connection, survey_id: uuid.UUID, question_id: str, response_ids: list[uuid.UUID]) -> list[Stored]:
    rows = await c.fetch("""select s.response_id, r.locale, s.label, s.confidence, s.source from answer_sentiment s join responses r on r.org_id=s.org_id and r.id=s.response_id
        where r.survey_id=$1 and s.question_id=$2 and s.response_id = any($3::uuid[])""", survey_id, question_id, response_ids)
    return [Stored.model_validate(dict(r)) for r in rows]


async def models_used(c: asyncpg.Connection, survey_id: uuid.UUID, question_id: str) -> list[str]:
    rows = await c.fetch("""select distinct s.model from answer_sentiment s join responses r on r.org_id=s.org_id and r.id=s.response_id
        where r.survey_id=$1 and s.question_id=$2 order by 1""", survey_id, question_id)
    return [r["model"] for r in rows]
