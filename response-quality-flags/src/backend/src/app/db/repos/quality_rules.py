"""SQL for quality_rules (per-survey data-quality rule sets)."""
import uuid
from typing import Any

import asyncpg


async def get(c: asyncpg.Connection, survey_id: uuid.UUID) -> Any:
    """The stored rules (JSON text or decoded JSON), or None when the survey has none."""
    return await c.fetchval("select rules from quality_rules where survey_id=$1", survey_id)


async def upsert(c: asyncpg.Connection, org_id: uuid.UUID, survey_id: uuid.UUID, rules_json: str) -> None:
    await c.execute("insert into quality_rules(org_id,survey_id,rules) values($1,$2,$3) on conflict (org_id,survey_id) do update set rules=excluded.rules, updated_at=now()", org_id, survey_id, rules_json)
