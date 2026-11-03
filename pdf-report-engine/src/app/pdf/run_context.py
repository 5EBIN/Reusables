"""
What ran, stamped into every artifact. One run context per package: the same run_id, the same generated_at and the same run_outcome in every document,
so a package from an aborted run can never be mistaken for a completed one, and two packages are told apart by run_id (storage keys are versioned by it).
"""
from __future__ import annotations

import uuid
from datetime import datetime

COMPLETED = "completed"
ABORTED = "aborted"


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def new_run_context(run_outcome: str = COMPLETED, *, trigger: str = "", abort_reason: str | None = None, generated_at: str | None = None,
                    run_id: str | None = None) -> dict:
    return {"run_id": run_id or uuid.uuid4().hex, "run_outcome": run_outcome, "trigger": trigger, "abort_reason": abort_reason,
            "generated_at": generated_at or now_iso()}


def header(ctx: dict | None, document: str) -> dict:
    """The block every JSON artifact starts with."""
    ctx = ctx or new_run_context()
    out = {"document": document, "generated_at": ctx["generated_at"], "run_id": ctx["run_id"], "run_outcome": ctx["run_outcome"], "trigger": ctx.get("trigger", "")}
    if ctx.get("abort_reason"):
        out["abort_reason"] = str(ctx["abort_reason"])[:300]
    return out


def reference(prefix: str, project_id, ctx: dict | None) -> str:
    """A document reference built from the project id and the run id (e.g. REPORT-1A2B3C4D-9F8E7D6C): stable per run, never derived from a name."""
    import re
    ctx = ctx or new_run_context()
    clean = lambda v: re.sub(r"[^A-Za-z0-9]", "", str(v or ""))[:8].upper() or "UNKNOWN"      # noqa: E731
    return f"{prefix}-{clean(project_id)}-{clean(ctx['run_id'])}"


def line(ctx: dict | None) -> str:
    """The one-line stamp for PDFs and markdown."""
    ctx = ctx or new_run_context()
    text = f"Run {ctx['run_id'][:8]} | outcome: {ctx['run_outcome']} | generated {ctx['generated_at']}"
    if ctx["run_outcome"] != COMPLETED:
        text += f" | THIS PACKAGE COMES FROM AN {str(ctx['run_outcome']).upper()} RUN"
    return text
