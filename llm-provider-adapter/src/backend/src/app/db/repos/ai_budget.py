"""SQL for the org's daily AI limits (org_settings) and what was really used (ai_usage per day, ai_calls per answer)."""
import uuid
from decimal import Decimal

import asyncpg
from pydantic import BaseModel


class Caps(BaseModel):
    tokens: int | None
    usd: Decimal | None


class Used(BaseModel):
    tokens: int
    usd: Decimal


async def caps(c: asyncpg.Connection) -> Caps:
    r = await c.fetchrow("select ai_daily_tokens as tokens, ai_daily_usd as usd from org_settings")
    return Caps(tokens=r["tokens"] if r else None, usd=r["usd"] if r else None)


async def used_today(c: asyncpg.Connection) -> Used:
    r = await c.fetchrow("select coalesce(sum(tokens),0)::bigint tokens, coalesce(sum(cost_usd),0) usd from ai_usage where day = current_date")
    return Used(tokens=r["tokens"], usd=r["usd"])


async def record_call(c: asyncpg.Connection, org_id: uuid.UUID, task: str, model: str, generation_id: str | None, prompt: int, completion: int, cost: float | None,
                      attempt: int, reasked: bool, provider: str | None = None) -> None:
    """One answer from the provider: the log row and today's total (one row per org per day)."""
    await c.execute("insert into ai_calls(org_id,id,task,model,generation_id,prompt_tokens,completion_tokens,cost_usd,attempt,reasked,provider) values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)",
                    org_id, uuid.uuid4(), task, model, generation_id, prompt, completion, cost, attempt, reasked, provider)
    await c.execute("insert into ai_usage(org_id,day,tokens,cost_usd) values($1,current_date,$2,$3) on conflict (org_id,day) do update "
                    "set tokens = ai_usage.tokens + excluded.tokens, cost_usd = ai_usage.cost_usd + excluded.cost_usd", org_id, prompt + completion, cost or 0)
