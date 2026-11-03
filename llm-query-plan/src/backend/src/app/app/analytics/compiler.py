"""QueryPlan -> (sql, params). Positional $n params only; identifiers only from the registry."""
import re
import uuid
from dataclasses import dataclass

from app.app.analytics.semantic import DIMS, METRICS
from app.core.query_plan import DimId, MetricId, QueryPlan

CAP = 5000
GROUPABLE = {DimId.SURVEY, DimId.DAY, DimId.WEEK, DimId.MONTH, DimId.LOCALE, DimId.COLLECTOR}
FUZZY = 0.3


class CompileError(Exception):
    """kind: CLARIFY | CANT_YET | REFUSE"""
    def __init__(self, kind: str, msg: str):
        super().__init__(msg)
        self.kind, self.msg = kind, msg


@dataclass
class Compiled:
    sql: str
    params: list
    group_cols: list[str]
    metric: MetricId
    denom_sql: str | None = None     # THEME_SHARE: per-group denominator (answers tagged)
    denom_params: list | None = None


_OPS = re.compile(r"""^[\s\-+!"'()|&<>:*~^\\]+""")


def clean_term(t: str) -> str:
    """Strip leading tsquery operators/quotes; they would change semantics."""
    t = _OPS.sub("", t).strip()
    return re.sub(r"[\"'\\]", " ", t).strip()


def _filter_clause(f, params: list) -> str:
    expr, kind = DIMS[f.dim]
    if f.dim in (DimId.DAY, DimId.WEEK, DimId.MONTH, DimId.THEME):
        raise CompileError("CANT_YET", f"filtering by {f.dim.value} is not supported")
    vals = f.value if isinstance(f.value, list) else [f.value]
    if kind == "uuid":
        try:
            vals = [uuid.UUID(v) for v in vals]
        except ValueError:
            raise CompileError("CLARIFY", f"{f.dim.value.lower()} id is not valid") from None
    if f.op == "in":
        params.append(vals)
        return f"{expr} = any(${len(params)})"
    params.append(vals[0])
    return f"{expr} {'=' if f.op == 'eq' else '<>'} ${len(params)}"


def _need(plan, m):
    present = {f.dim for f in plan.filters if f.op in ("eq", "in")}
    for need in m.requires:
        if need not in present:
            raise CompileError("CLARIFY", f"Which {'survey' if need is DimId.SURVEY else 'question'}?")


def _value(plan, dim):
    for f in plan.filters:
        if f.dim is dim and f.op == "eq":
            return f.value
    return None


def compile_plan(plan: QueryPlan) -> Compiled:
    if plan.metric is None:
        raise CompileError("CLARIFY", plan.clarify_question or "Which metric do you want?")
    m = METRICS[plan.metric]
    if plan.date_range is None:
        raise CompileError("CLARIFY", "Which date range? (start and end dates are required)")
    _need(plan, m)
    for d in plan.dimensions:
        if d not in GROUPABLE:
            raise CompileError("CANT_YET", f"grouping by {d.value} is not supported")
    if len(set(plan.dimensions)) != len(plan.dimensions):
        raise CompileError("CLARIFY", "duplicate dimensions")
    if plan.text_match is not None and plan.metric is not MetricId.RESPONSE_COUNT:
        raise CompileError("CANT_YET", "text search is only supported with the response count metric")
    if plan.breakdown_question and plan.metric in (MetricId.RESPONSE_COUNT, MetricId.COMPLETION_RATE):
        raise CompileError("CANT_YET", "breakdown by question needs an answer-based metric")

    params: list = [plan.date_range.start, plan.date_range.end]
    where = ["r.received_at >= ($1::date)::timestamp at time zone 'Asia/Dubai'",
             "r.received_at < (($2::date) + 1)::timestamp at time zone 'Asia/Dubai'",
             "not r.excluded"]
    theme = plan.metric is MetricId.THEME_SHARE
    joins = ""
    sel_extra: list[str] = []
    if theme:
        sid = _value(plan, DimId.SURVEY)
        q = _value(plan, DimId.QUESTION)
        if sid is None or q is None:
            raise CompileError("CLARIFY", "Which survey and question?")
        try:
            sid_u = uuid.UUID(sid)
        except ValueError:
            raise CompileError("CLARIFY", "survey id is not valid") from None
        params += [sid_u, q]
        si, qi = len(params) - 1, len(params)
        tax = (f"(select tx.version from taxonomies tx where tx.survey_id = ${si} and tx.question_id = ${qi} "
               f"and tx.status = 'frozen' order by tx.version desc limit 1)")
        frm = ("answer_tags g join responses r on r.org_id = g.org_id and r.id = g.response_id "
               "cross join lateral unnest(case when g.unclassified then array['__unclassified'] else g.themes end) as u(theme)")
        clf = (f"g.classifier_version = (select tx.active_classifier from taxonomies tx where tx.survey_id = ${si} "
               f"and tx.question_id = ${qi} and tx.version = g.taxonomy_version)")
        base = [f"g.question_id = ${qi}", f"g.taxonomy_version = {tax}", clf]
        where += base
        sel_extra.append("u.theme as theme")
    elif m.needs_answers:
        frm = "responses r join answers a on a.org_id = r.org_id and a.response_id = r.id"
        where.append("a.value_num is not null" if plan.metric in (MetricId.NPS, MetricId.AVG_RATING)
                     else "a.value_choice is not null")
    else:
        frm = "responses r"
    if plan.text_match is not None:
        frm += " join answers a on a.org_id = r.org_id and a.response_id = r.id and a.value_text is not null"
        conds = []
        for t in plan.text_match.terms:
            term = clean_term(t)
            if not term:
                raise CompileError("CLARIFY", "search term has no usable characters")
            params.append(term)
            i = len(params)
            conds.append(f"(a.search_vector @@ websearch_to_tsquery('simple', app.ar_norm(${i})) "
                         f"or similarity(a.text_norm, app.ar_norm(${i})) > {FUZZY})")
        where.append("(" + (" and " if plan.text_match.mode == "all" else " or ").join(conds) + ")")
        q = _value(plan, DimId.QUESTION)
        if q is not None:
            params.append(q)
            where.append(f"a.question_id = ${len(params)}")
    if plan.breakdown_question:
        params.append(plan.breakdown_question)
        joins = (f" join answers b on b.org_id = r.org_id and b.response_id = r.id and b.question_id = ${len(params)} "
                 "and b.value_choice is not null")
        sel_extra.append("b.value_choice as breakdown")
    frm += joins
    for f in plan.filters:
        if theme and f.dim in (DimId.SURVEY, DimId.QUESTION):
            continue
        if plan.text_match is not None and f.dim is DimId.QUESTION:
            continue
        if f.dim is DimId.QUESTION and not (m.needs_answers or theme):
            raise CompileError("CANT_YET", "question filter needs an answer-based metric")
        where.append(_filter_clause(f, params))
        if f.dim is DimId.QUESTION and m.needs_answers and not theme:
            pass
    gcols = [f"{DIMS[d][0]} as g{i}" for i, d in enumerate(plan.dimensions)]
    if plan.metric is MetricId.CHOICE_SHARE:
        gcols.append("a.value_choice as choice")
    gcols += sel_extra
    group_names = [c.split(" as ")[1] for c in gcols]
    select_agg = "count(*) as n" if plan.text_match is None else "count(distinct r.id) as n"
    if not theme and plan.text_match is None:
        select_agg = m.select
    sql = f"select {', '.join(gcols + [select_agg])} from {frm} where {' and '.join(where)}"
    denom = None
    if group_names:
        sql += " group by " + ", ".join(str(i + 1) for i in range(len(group_names)))
        sql += " order by " + ", ".join(str(i + 1) for i in range(len(group_names)))
    sql += f" limit {CAP + 1}"
    if theme:
        other = [c for c in group_names if c != "theme"]
        dcols = [c for c in gcols if not c.endswith("as theme")]
        dfrm = "answer_tags g join responses r on r.org_id = g.org_id and r.id = g.response_id" + joins
        dsel = ", ".join(dcols + ["count(*) as n"])
        denom = f"select {dsel} from {dfrm} where {' and '.join(where)}"
        if other:
            denom += " group by " + ", ".join(str(i + 1) for i in range(len(other)))
    return Compiled(sql, params, group_names, plan.metric, denom, params if denom else None)
