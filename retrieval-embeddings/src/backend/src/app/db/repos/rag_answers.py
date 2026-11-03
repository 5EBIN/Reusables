"""SQL for rag_answers ("Ask your survey" answers; append-only) and the analysis_runs record kept for each. SQL text is unchanged from the router it was moved out of."""
import uuid
from datetime import datetime
from typing import Any

import asyncpg
from pydantic import BaseModel


class StoredAnswer(BaseModel):
    id: uuid.UUID
    answer: Any                      # dict or JSON text
    status: str
    model: str
    prompt_version: str
    inputs_hash: str
    retrieved_ids: list[uuid.UUID]


class HistoryRow(StoredAnswer):
    question: str
    filters: Any                     # dict or JSON text
    created_at: datetime


async def by_inputs_hash(c: asyncpg.Connection, org_id: uuid.UUID, inputs_hash: str) -> StoredAnswer | None:
    r = await c.fetchrow("select id, answer, status, model, prompt_version, inputs_hash, retrieved_ids from rag_answers where org_id=$1 and inputs_hash=$2", org_id, inputs_hash)
    return StoredAnswer.model_validate(dict(r)) if r else None


async def insert(c: asyncpg.Connection, org_id: uuid.UUID, answer_id: uuid.UUID, survey_id: uuid.UUID, question_id: str, asked_by: uuid.UUID, question: str,
                 filters_json: str, retrieved_ids: list[uuid.UUID], answer_json: str, status: str, model: str, prompt_version: str, inputs_hash: str) -> uuid.UUID | None:
    """The new id, or None when an answer with the same inputs hash already exists."""
    return await c.fetchval("insert into rag_answers(org_id,id,survey_id,question_id,asked_by,question,filters,retrieved_ids,answer,status,model,prompt_version,inputs_hash) "
                            "values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) on conflict (org_id,inputs_hash) do nothing returning id",
                            org_id, answer_id, survey_id, question_id, asked_by, question, filters_json, retrieved_ids, answer_json, status, model, prompt_version, inputs_hash)


async def history(c: asyncpg.Connection, survey_id: uuid.UUID, question_id: str, asked_by: uuid.UUID, limit: int) -> list[HistoryRow]:
    rows = await c.fetch("select id, question, filters, answer, status, model, prompt_version, inputs_hash, retrieved_ids, created_at from rag_answers "
                         "where survey_id=$1 and question_id=$2 and asked_by=$3 order by created_at desc, id desc limit $4", survey_id, question_id, asked_by, limit)
    return [HistoryRow.model_validate(dict(r)) for r in rows]
