"""SQL for answer_tags (theme tags a classifier assigned to each answer)."""
import uuid
from typing import Any

import asyncpg
from pydantic import BaseModel


class TagRow(BaseModel):
    response_id: uuid.UUID
    themes: list[str]


async def for_responses(c: asyncpg.Connection, question_id: str, taxonomy_version: int, classifier_version: Any, response_ids: list[uuid.UUID]) -> list[TagRow]:
    rows = await c.fetch("select response_id, themes from answer_tags where question_id=$1 and taxonomy_version=$2 and classifier_version=$3 and response_id = any($4::uuid[])",
                         question_id, taxonomy_version, classifier_version, response_ids)
    return [TagRow.model_validate(dict(r)) for r in rows]


async def ordered_for_responses(c: asyncpg.Connection, question_id: str, taxonomy_version: int, classifier_version: Any, response_ids: list[uuid.UUID]) -> list[TagRow]:
    rows = await c.fetch("select response_id, themes from answer_tags where question_id=$1 and taxonomy_version=$2 and classifier_version=$3 and response_id = any($4::uuid[]) order by response_id",
                         question_id, taxonomy_version, classifier_version, response_ids)
    return [TagRow.model_validate(dict(r)) for r in rows]


async def all_for_version(c: asyncpg.Connection, question_id: str, taxonomy_version: int, classifier_version: Any) -> list[TagRow]:
    rows = await c.fetch("select response_id, themes from answer_tags where question_id=$1 and taxonomy_version=$2 and classifier_version=$3", question_id, taxonomy_version, classifier_version)
    return [TagRow.model_validate(dict(r)) for r in rows]


class TagFull(BaseModel):
    response_id: uuid.UUID
    themes: list[str]
    sentiment: int | None
    sentiment_conf: float | None
    unclassified: bool | None


async def upsert_tag(c: asyncpg.Connection, org_id: uuid.UUID, response_id: uuid.UUID, question_id: str, taxonomy_version: int, classifier_version: Any,
                     themes: list[str], sentiment: int, sentiment_conf: float, unclassified: bool) -> None:
    await c.execute("""insert into answer_tags(org_id,response_id,question_id,taxonomy_version,classifier_version,themes,sentiment,sentiment_conf,unclassified)
                    values($1,$2,$3,$4,$5,$6,$7,$8,$9) on conflict (org_id,response_id,question_id,taxonomy_version,classifier_version)
                    do update set themes=excluded.themes, sentiment=excluded.sentiment, sentiment_conf=excluded.sentiment_conf, unclassified=excluded.unclassified""",
                    org_id, response_id, question_id, taxonomy_version, classifier_version, themes, sentiment, sentiment_conf, unclassified)


async def for_analysis(c: asyncpg.Connection, survey_id: uuid.UUID, question_id: str, taxonomy_version: int, classifier_version: Any, response_ids: list[uuid.UUID]) -> list[TagFull]:
    rows = await c.fetch("""select g.response_id, g.themes, g.sentiment, g.sentiment_conf, g.unclassified from answer_tags g join responses r on r.org_id=g.org_id and r.id=g.response_id
                where r.survey_id=$1 and g.question_id=$2 and g.taxonomy_version=$3 and g.classifier_version=$4 and g.response_id = any($5::uuid[])""",
                         survey_id, question_id, taxonomy_version, classifier_version, response_ids)
    return [TagFull.model_validate(dict(r)) for r in rows]
