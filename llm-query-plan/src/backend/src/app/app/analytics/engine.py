"""Run a QueryPlan: compile -> execute read-only with timeout -> shape result with n, CI, scope_echo."""
import math
from datetime import date
from typing import Any, assert_never

import asyncpg

from app.app.analytics.compiler import CAP, CompileError, compile_plan
from app.app.analytics.semantic import METRICS
from app.core.query_plan import MIN_N, MetricId, Outcome, QueryPlan


def nps_ci(promoters: int, detractors: int, n: int) -> tuple[int, int]:
    """95% CI, normal approximation: se = sqrt((p + d - (p-d)^2) / n)."""
    p, d = promoters / n, detractors / n
    se = math.sqrt(max(p + d - (p - d) ** 2, 0) / n)
    v = 100 * (p - d)
    return max(-100, round(v - 196 * se)), min(100, round(v + 196 * se))


def _cell(v: Any):
    return str(v) if isinstance(v, (date,)) or hasattr(v, "hex") else v


def scope_echo(plan: QueryPlan, n: int | None, excluded: int | None) -> str:
    m = METRICS[plan.metric].label if plan.metric else "?"
    dr = plan.date_range
    parts = [m, f"{dr.start}..{dr.end}" if dr else "no range"]
    col = [f for f in plan.filters if f.dim.value == "COLLECTOR"]
    parts.append("collector filtered" if col else "all collectors")
    if n is not None:
        parts.append(f"n={n}")
    if excluded:
        parts.append(f"{excluded} excluded")
    return " · ".join(parts)


def _resp(outcome: Outcome, **kw) -> dict:
    return {"outcome": outcome.value, "scope_echo": None, "metric": None, "columns": [], "rows": [], "n": None,
            "truncated": False, "ci95": None, "clarify_question": None, "reason": None, **kw}


async def run_query(conn: asyncpg.Connection, plan: QueryPlan, timeout_ms: int = 5000) -> dict:
    match plan.outcome:
        case Outcome.CLARIFY:
            return _resp(Outcome.CLARIFY, clarify_question=plan.clarify_question or "Could you clarify?")
        case Outcome.CANT_YET:
            return _resp(Outcome.CANT_YET, reason=plan.reason or "not supported yet")
        case Outcome.REFUSE:
            return _resp(Outcome.REFUSE, reason=plan.reason or "out of scope")
        case Outcome.ANSWER:
            return await _answer(conn, plan, timeout_ms)
        case _:
            assert_never(plan.outcome)


async def _answer(conn, plan: QueryPlan, timeout_ms: int) -> dict:
    try:
        c = compile_plan(plan)
    except CompileError as e:
        if e.kind == "CLARIFY":
            return _resp(Outcome.CLARIFY, clarify_question=e.msg)
        if e.kind == "REFUSE":
            return _resp(Outcome.REFUSE, reason=e.msg)
        return _resp(Outcome.CANT_YET, reason=e.msg)
    await conn.execute("set local transaction_read_only = on")
    await conn.execute(f"set local statement_timeout = {int(timeout_ms)}")
    try:
        rows = await conn.fetch(c.sql, *c.params)
    except asyncpg.QueryCanceledError:
        return _resp(Outcome.CANT_YET, reason="query timed out; narrow the date range")
    truncated = len(rows) > CAP
    rows = rows[:CAP]
    meta = METRICS[c.metric]
    cols = c.group_cols
    out_rows, total_n = [], 0
    if c.metric is MetricId.THEME_SHARE:
        denoms = {}
        for d in await conn.fetch(c.denom_sql, *c.denom_params):
            denoms[tuple(_cell(d[k]) for k in cols if k != "theme")] = d["n"]
        for r in rows:
            key = tuple(_cell(r[k]) for k in cols if k != "theme")
            den = denoms.get(key, 0)
            d = {k: _cell(r[k]) for k in cols}
            if d["theme"] == "__unclassified":
                d["theme"] = "unclassified"
            d.update(n=r["n"], n_total=den)
            if den < MIN_N:
                d.update(value=None, share=None, suppressed=True)
            else:
                d.update(value=r["n"], share=round(100 * r["n"] / den, 1))
            out_rows.append(d)
        total_n = sum(denoms.values())
    else:
        for r in rows:
            d = {k: _cell(r[k]) for k in cols}
            n = r["n"]
            total_n += n
            if meta.min_n and n < MIN_N:
                d.update(n=n, value=None, suppressed=True)
            elif c.metric is MetricId.NPS:
                d.update(n=n, value=round(100 * (r["promoters"] - r["detractors"]) / n),
                         promoters=r["promoters"], detractors=r["detractors"], passives=n - r["promoters"] - r["detractors"],
                         ci95=list(nps_ci(r["promoters"], r["detractors"], n)))
            elif c.metric is MetricId.AVG_RATING:
                d.update(n=n, value=round(float(r["avg"]), 2))
            elif c.metric is MetricId.COMPLETION_RATE:
                d.update(n=n, value=round(100 * r["completed"] / n, 1))
            else:
                d.update(n=n, value=n)
            out_rows.append(d)
    if c.metric is MetricId.CHOICE_SHARE:
        denom: dict = {}
        for d in out_rows:
            key = tuple(d[k] for k in cols if k != "choice")
            denom[key] = denom.get(key, 0) + d["n"]
        for d in out_rows:
            if not d.get("suppressed"):
                d["share"] = round(100 * d["n"] / denom[tuple(d[k] for k in cols if k != "choice")], 1)
    if meta.min_n and out_rows and all(d.get("suppressed") for d in out_rows):
        return _resp(Outcome.CANT_YET, reason=f"n too small (fewer than {MIN_N} responses)", metric=c.metric.value)
    if not out_rows:
        if meta.min_n:
            return _resp(Outcome.CANT_YET, reason="no data in this scope", metric=c.metric.value)
        out_rows = [{"n": 0, "value": 0}]
    excl = await conn.fetchval(
        "select count(*) from responses r where r.excluded and r.received_at >= ($1::date)::timestamp at time zone 'Asia/Dubai' "
        "and r.received_at < (($2::date)+1)::timestamp at time zone 'Asia/Dubai'", plan.date_range.start, plan.date_range.end)
    top = out_rows[0] if len(out_rows) == 1 and not cols else None
    return _resp(Outcome.ANSWER, metric=c.metric.value, columns=cols + ["n", "value"], rows=out_rows,
                 n=total_n, truncated=truncated, ci95=(top or {}).get("ci95"),
                 scope_echo=scope_echo(plan, total_n, excl), excluded=excl)
