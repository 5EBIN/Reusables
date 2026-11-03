"""SQL for theme_assignments (method='semantic' rows written by an assignment run). SQL text is unchanged from the router it was moved out of."""
import uuid
from typing import Any

import asyncpg
from pydantic import BaseModel


class AssignmentRun(BaseModel):
    run_id: uuid.UUID
    taxonomy_version: int
    model_id: str


class Assignment(BaseModel):
    response_id: uuid.UUID
    theme_key: str
    score: float
    band: str


async def insert_semantic(c: asyncpg.Connection, org_id: uuid.UUID, survey_id: uuid.UUID, question_id: str, taxonomy_version: int, response_id: uuid.UUID,
                          theme_key: Any, score: float, band: str, model_id: str, run_id: uuid.UUID) -> None:
    await c.execute("insert into theme_assignments(org_id,survey_id,question_id,taxonomy_version,response_id,theme_key,score,band,method,model_id,run_id) "
                    "values($1,$2,$3,$4,$5,$6,$7,$8,'semantic',$9,$10)", org_id, survey_id, question_id, taxonomy_version, response_id, theme_key, score, band, model_id, run_id)


async def latest_run(c: asyncpg.Connection, survey_id: uuid.UUID, question_id: str, taxonomy_version: int | None) -> AssignmentRun | None:
    r = await c.fetchrow("select run_id, taxonomy_version, model_id from theme_assignments where survey_id=$1 and question_id=$2 and ($3::int is null or taxonomy_version=$3) "
                         "order by created_at desc, run_id desc limit 1", survey_id, question_id, taxonomy_version)
    return AssignmentRun.model_validate(dict(r)) if r else None


async def for_run(c: asyncpg.Connection, run_id: uuid.UUID) -> list[Assignment]:
    rows = await c.fetch("select response_id, theme_key, score, band from theme_assignments where run_id=$1 order by response_id", run_id)
    return [Assignment.model_validate(dict(r)) for r in rows]
