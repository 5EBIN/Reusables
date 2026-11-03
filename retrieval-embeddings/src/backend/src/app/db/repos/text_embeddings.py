"""SQL for text_embeddings (stored vectors of open-text answers; append-only)."""
import uuid

import asyncpg
from pydantic import BaseModel


class StoredVector(BaseModel):
    response_id: uuid.UUID
    source_hash: str
    dim: int
    v: list[float]


async def vectors_for(c: asyncpg.Connection, question_id: str, model_id: str, dim: int, response_ids: list[uuid.UUID]) -> list[StoredVector]:
    """Newest first, so the first row per response is the current vector."""
    rows = await c.fetch("select response_id, source_hash, dim, vec::real[] as v from text_embeddings where question_id=$1 and model_id=$2 and dim=$3 and response_id = any($4::uuid[]) "
                         "order by created_at desc", question_id, model_id, dim, response_ids)
    return [StoredVector.model_validate(dict(r)) for r in rows]


async def count_from_other_models(c: asyncpg.Connection, question_id: str, model_id: str, response_ids: list[uuid.UUID]) -> int:
    return await c.fetchval("select count(*) from text_embeddings where question_id=$1 and model_id<>$2 and response_id = any($3::uuid[])", question_id, model_id, response_ids)


class Nearest(BaseModel):
    response_id: uuid.UUID
    score: float


async def existing_hashes(c: asyncpg.Connection, question_id: str, model_id: str, response_ids: list[uuid.UUID]) -> set[tuple[str, str]]:
    """(response id, source hash) pairs already embedded with this model."""
    rows = await c.fetch("select response_id, source_hash from text_embeddings where question_id=$1 and model_id=$2 and response_id = any($3::uuid[])", question_id, model_id, response_ids)
    return {(str(r["response_id"]), r["source_hash"]) for r in rows}


async def insert(c: asyncpg.Connection, org_id: uuid.UUID, response_id: uuid.UUID, question_id: str, model_id: str, dim: int, source_hash: str, vec_literal: str) -> None:
    """Append-only; a repeat of the same (response, model, source hash) is ignored."""
    await c.execute("insert into text_embeddings(org_id,response_id,question_id,model_id,dim,source_hash,vec) values($1,$2,$3,$4,$5,$6,$7::text::vector) on conflict do nothing",
                    org_id, response_id, question_id, model_id, dim, source_hash, vec_literal)


async def nearest(c: asyncpg.Connection, query_vec_literal: str, question_id: str, model_id: str, dim: int, response_ids: list[uuid.UUID], source_hashes: list[str], k: int) -> list[Nearest]:
    """Closest stored vectors by cosine distance; only rows whose (response id, source hash) pair is given are considered."""
    rows = await c.fetch("""select e.response_id, 1 - (e.vec <=> $1::text::vector) as score from text_embeddings e where e.question_id=$2 and e.model_id=$3 and e.dim=$4
            and (e.response_id, e.source_hash) in (select * from unnest($5::uuid[], $6::text[])) order by e.vec <=> $1::text::vector, e.response_id limit $7""",
                         query_vec_literal, question_id, model_id, dim, response_ids, source_hashes, k)
    return [Nearest.model_validate(dict(r)) for r in rows]
