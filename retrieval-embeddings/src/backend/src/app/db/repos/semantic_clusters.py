"""SQL for semantic_clusters, their members and their labels (append-only). SQL text is unchanged from the router it was moved out of."""
import uuid
from datetime import datetime
from typing import Any

import asyncpg
from pydantic import BaseModel


class ClusterRun(BaseModel):
    run_id: uuid.UUID
    model_id: str
    k: int
    params: Any                      # dict or JSON text
    created_at: datetime


class Member(BaseModel):
    response_id: uuid.UUID
    cluster_no: int
    distance: float


class Label(BaseModel):
    cluster_no: int
    label: str
    description: str | None


async def run_for_inputs_hash(c: asyncpg.Connection, inputs_hash: str) -> uuid.UUID | None:
    return await c.fetchval("select run_id from semantic_clusters where inputs_hash=$1", inputs_hash)


async def insert_run(c: asyncpg.Connection, org_id: uuid.UUID, run_id: uuid.UUID, survey_id: uuid.UUID, question_id: str, model_id: str, k: int,
                     params_json: str, inputs_hash: str) -> uuid.UUID | None:
    """The new run id, or None when a run with the same inputs hash already exists."""
    return await c.fetchval("insert into semantic_clusters(org_id,run_id,survey_id,question_id,model_id,k,params,inputs_hash) values($1,$2,$3,$4,$5,$6,$7,$8) "
                            "on conflict (org_id,inputs_hash) do nothing returning run_id", org_id, run_id, survey_id, question_id, model_id, k, params_json, inputs_hash)


async def insert_member(c: asyncpg.Connection, org_id: uuid.UUID, run_id: uuid.UUID, response_id: uuid.UUID, cluster_no: int, distance: float) -> None:
    await c.execute("insert into semantic_cluster_members(org_id,run_id,response_id,cluster_no,distance) values($1,$2,$3,$4,$5)", org_id, run_id, response_id, cluster_no, distance)


async def insert_label(c: asyncpg.Connection, org_id: uuid.UUID, run_id: uuid.UUID, cluster_no: int, label: str, description: str | None,
                       verbatim_ids: list[uuid.UUID], model: str) -> None:
    """A label proposed by the model (the router only passes labels that passed verification)."""
    await c.execute("insert into semantic_cluster_labels(org_id,run_id,cluster_no,label,description,verbatim_ids,proposed_by,model) values($1,$2,$3,$4,$5,$6,'llm',$7)",
                    org_id, run_id, cluster_no, label, description, verbatim_ids, model)


async def latest_run(c: asyncpg.Connection, survey_id: uuid.UUID, question_id: str) -> ClusterRun | None:
    r = await c.fetchrow("select run_id, model_id, k, params, created_at from semantic_clusters where survey_id=$1 and question_id=$2 order by created_at desc, run_id desc limit 1", survey_id, question_id)
    return ClusterRun.model_validate(dict(r)) if r else None


async def members(c: asyncpg.Connection, run_id: uuid.UUID) -> list[Member]:
    rows = await c.fetch("select response_id, cluster_no, distance from semantic_cluster_members where run_id=$1 order by cluster_no, distance, response_id", run_id)
    return [Member.model_validate(dict(r)) for r in rows]


async def labels(c: asyncpg.Connection, run_id: uuid.UUID) -> dict[int, Label]:
    rows = await c.fetch("select cluster_no, label, description from semantic_cluster_labels where run_id=$1", run_id)
    return {r["cluster_no"]: Label.model_validate(dict(r)) for r in rows}
