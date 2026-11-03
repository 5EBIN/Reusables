"""SQL for taxonomies (versioned theme sets per survey question)."""
import uuid
from typing import Any

import asyncpg
from pydantic import BaseModel


class Taxonomy(BaseModel):
    version: int
    active_classifier: Any


async def latest_frozen(c: asyncpg.Connection, survey_id: uuid.UUID, question_id: str) -> Taxonomy | None:
    r = await c.fetchrow("select version, active_classifier from taxonomies where survey_id=$1 and question_id=$2 and status='frozen' order by version desc limit 1", survey_id, question_id)
    return Taxonomy.model_validate(dict(r)) if r else None


async def status_of(c: asyncpg.Connection, survey_id: uuid.UUID, question_id: str, version: int) -> str | None:
    return await c.fetchval("select status from taxonomies where survey_id=$1 and question_id=$2 and version=$3", survey_id, question_id, version)


async def active_classifier(c: asyncpg.Connection, survey_id: uuid.UUID, question_id: str, version: int) -> Any:
    return await c.fetchval("select active_classifier from taxonomies where survey_id=$1 and question_id=$2 and version=$3", survey_id, question_id, version)


class TaxonomyVersion(BaseModel):
    version: int
    status: str
    multi_label: bool
    active_classifier: Any


class FrozenTaxonomy(BaseModel):
    version: int
    active_classifier: Any
    approved_at: Any


async def versions(c: asyncpg.Connection, survey_id: uuid.UUID, question_id: str) -> list[TaxonomyVersion]:
    rows = await c.fetch("select version, status, multi_label, active_classifier from taxonomies where survey_id=$1 and question_id=$2 order by version", survey_id, question_id)
    return [TaxonomyVersion.model_validate(dict(r)) for r in rows]


async def next_version(c: asyncpg.Connection, survey_id: uuid.UUID, question_id: str) -> int:
    return (await c.fetchval("select coalesce(max(version),0) from taxonomies where survey_id=$1 and question_id=$2", survey_id, question_id)) + 1


async def insert(c: asyncpg.Connection, org_id: uuid.UUID, survey_id: uuid.UUID, question_id: str, version: int) -> None:
    await c.execute("insert into taxonomies(org_id,survey_id,question_id,version) values($1,$2,$3,$4)", org_id, survey_id, question_id, version)


async def freeze(c: asyncpg.Connection, survey_id: uuid.UUID, question_id: str, version: int, approved_by: uuid.UUID) -> None:
    await c.execute("update taxonomies set status='frozen', approved_by=$4, approved_at=now(), frozen_at=now() where survey_id=$1 and question_id=$2 and version=$3", survey_id, question_id, version, approved_by)


async def set_active_classifier(c: asyncpg.Connection, survey_id: uuid.UUID, question_id: str, version: int, classifier_version: Any) -> None:
    await c.execute("update taxonomies set active_classifier=$4 where survey_id=$1 and question_id=$2 and version=$3", survey_id, question_id, version, classifier_version)


async def latest_frozen_with_approval(c: asyncpg.Connection, survey_id: uuid.UUID, question_id: str) -> FrozenTaxonomy | None:
    r = await c.fetchrow("select version, active_classifier, approved_at from taxonomies where survey_id=$1 and question_id=$2 and status='frozen' "
                         "order by version desc limit 1", survey_id, question_id)
    return FrozenTaxonomy.model_validate(dict(r)) if r else None
