"""SQL for themes (the named topics of a question's taxonomy). SQL text is unchanged from the router it was moved out of."""
import uuid
from typing import Any

import asyncpg
from pydantic import BaseModel


class Theme(BaseModel):
    id: uuid.UUID
    key: str
    label: Any                       # JSON text of {lang: label}
    definition: str | None
    status: str
    keywords: list[str]
    merged_into: uuid.UUID | None


async def for_taxonomy(c: asyncpg.Connection, survey_id: uuid.UUID, question_id: str, version: int) -> list[Theme]:
    rows = await c.fetch("select id, key, label, definition, status, keywords, merged_into from themes where survey_id=$1 and question_id=$2 "
                         "and taxonomy_version=$3 order by key", survey_id, question_id, version)
    return [Theme.model_validate(dict(r)) for r in rows]


async def insert(c: asyncpg.Connection, org_id: uuid.UUID, theme_id: uuid.UUID, survey_id: uuid.UUID, question_id: str, version: int, key: str,
                 label_json: str, definition: str, keywords: list[str], created_by: uuid.UUID) -> None:
    await c.execute("insert into themes(org_id,id,survey_id,question_id,taxonomy_version,key,label,definition,keywords,created_by) "
                    "values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) on conflict do nothing", org_id, theme_id, survey_id, question_id, version, key, label_json, definition, keywords, created_by)


async def status_in_taxonomy(c: asyncpg.Connection, theme_id: uuid.UUID, survey_id: uuid.UUID, question_id: str, version: int) -> str | None:
    r = await c.fetchrow("select status from themes where id=$1 and survey_id=$2 and question_id=$3 and taxonomy_version=$4", theme_id, survey_id, question_id, version)
    return r["status"] if r else None


async def exists_in_taxonomy(c: asyncpg.Connection, theme_id: uuid.UUID, version: int, survey_id: uuid.UUID, question_id: str) -> bool:
    return bool(await c.fetchval("select 1 from themes where id=$1 and taxonomy_version=$2 and survey_id=$3 and question_id=$4", theme_id, version, survey_id, question_id))


async def keywords_of(c: asyncpg.Connection, theme_id: uuid.UUID) -> list[str]:
    return await c.fetchval("select keywords from themes where id=$1", theme_id)


async def add_keywords(c: asyncpg.Connection, theme_id: uuid.UUID, keywords: list[str]) -> None:
    """Merges the keywords into the theme without duplicates."""
    await c.execute("update themes set keywords = (select array(select distinct unnest(keywords || $2::text[]))) where id=$1", theme_id, keywords)


async def reject_merged(c: asyncpg.Connection, theme_id: uuid.UUID, merged_into: uuid.UUID, decided_by: uuid.UUID) -> None:
    await c.execute("update themes set status='rejected', merged_into=$2, decided_by=$3 where id=$1", theme_id, merged_into, decided_by)


async def set_status(c: asyncpg.Connection, theme_id: uuid.UUID, status: str, decided_by: uuid.UUID) -> None:
    await c.execute("update themes set status=$2, decided_by=$3 where id=$1", theme_id, status, decided_by)


async def rename(c: asyncpg.Connection, theme_id: uuid.UUID, survey_id: uuid.UUID, question_id: str, version: int, label_json: str) -> bool:
    """True when the theme matched."""
    r = await c.execute("update themes set label=$5 where id=$1 and survey_id=$2 and question_id=$3 and taxonomy_version=$4", theme_id, survey_id, question_id, version, label_json)
    return not r.endswith(" 0")


async def approved_count(c: asyncpg.Connection, survey_id: uuid.UUID, question_id: str, version: int) -> int:
    return await c.fetchval("select count(*) from themes where survey_id=$1 and question_id=$2 and taxonomy_version=$3 and status='approved'", survey_id, question_id, version)


async def freeze_approved(c: asyncpg.Connection, survey_id: uuid.UUID, question_id: str, version: int) -> None:
    await c.execute("update themes set status='frozen' where survey_id=$1 and question_id=$2 and taxonomy_version=$3 and status='approved'", survey_id, question_id, version)
