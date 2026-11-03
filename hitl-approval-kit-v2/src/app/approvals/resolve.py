"""Create and resolve approval requests.

Rules: a resolution is a STATUS (approved / rejected / revision_requested / expired), never a boolean; a revision request must carry feedback; resolving twice is idempotent
(the loser of a race gets the stored row back, never a second transition); an expired request is claimed with the same atomic UPDATE a person's decision uses.
Notifications are hooks (`on_request`, `on_resolve`): the host decides whether they go to a server-sent-event stream, a queue or nowhere.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.approvals.lifecycle import resolved_fields
from app._stubs import ApprovalRequest

logger = logging.getLogger(__name__)

STATUSES = ("approved", "rejected", "revision_requested", "expired")
Hook = Callable[[dict[str, Any]], Awaitable[None]]


class ApprovalError(ValueError):
    pass


async def create_request(owner_id: str, action: str, details: dict, db: AsyncSession, *, group_key: str | None = None, on_request: Hook | None = None) -> ApprovalRequest:
    """A pending request. With `group_key` (a key inside `details`) at most one pending request per (owner, action, details[group_key]) exists: a second caller gets the
    existing one back. The host enforces that with a partial unique index; the INSERT runs in a SAVEPOINT so a collision does not discard the caller's other work."""
    def build() -> ApprovalRequest:
        return ApprovalRequest(project_id=owner_id, action=action, details=details, status="pending")

    approval = build()
    try:
        async with db.begin_nested():
            db.add(approval)
            await db.flush()
    except IntegrityError:
        if not group_key:
            raise
        existing = (await db.execute(select(ApprovalRequest).where(
            ApprovalRequest.project_id == owner_id, ApprovalRequest.action == action, ApprovalRequest.status == "pending",
            ApprovalRequest.details[group_key].as_string() == details.get(group_key)))).scalar_one_or_none()
        if existing is not None:
            return existing
        approval = build()
        async with db.begin_nested():
            db.add(approval)
            await db.flush()
    if on_request:
        await on_request({"type": "approval_required", "approval_id": approval.id, "action": action, "details": details})
    return approval


async def resolve_request(approval_id: str, owner_id: str, status: str, db: AsyncSession, *, feedback: str = "", decided_by: str | None = None,
                          on_resolve: Hook | None = None) -> ApprovalRequest:
    """Atomic claim (UPDATE ... WHERE status = 'pending' ... RETURNING): only one caller can win. A caller that loses gets the stored row, so resolving is idempotent."""
    if status not in STATUSES:
        raise ApprovalError(f"unknown status {status!r}")
    if status == "revision_requested" and not (feedback or "").strip():
        raise ApprovalError("a revision request needs feedback")
    values = {"status": status, "decided_at": datetime.now(timezone.utc), "feedback": feedback or None}
    if decided_by:
        values["decided_by"] = str(decided_by)
    claim = await db.execute(update(ApprovalRequest).where(ApprovalRequest.id == approval_id, ApprovalRequest.project_id == owner_id, ApprovalRequest.status == "pending")
                             .values(**values).returning(ApprovalRequest.id))
    won = claim.scalar_one_or_none() is not None
    row = (await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id, ApprovalRequest.project_id == owner_id))).scalar_one_or_none()
    if row is None:
        raise ApprovalError(f"approval {approval_id} not found")
    if won and on_resolve:
        await on_resolve({"type": "approval_resolved", **resolved_fields(approval_id, status, row.action), "feedback": feedback or "", "revision": status == "revision_requested"})
    return row


async def expire_stale(db: AsyncSession, ttl: timedelta, *, on_resolve: Hook | None = None) -> list[str]:
    """Expire every pending request older than `ttl`; returns the ids this call expired. Safe under several replicas: the claim is one UPDATE ... RETURNING."""
    cutoff = datetime.now(timezone.utc) - ttl
    claimed = (await db.execute(update(ApprovalRequest).where(ApprovalRequest.status == "pending", ApprovalRequest.created_at < cutoff)
                                .values(status="expired", decided_at=datetime.now(timezone.utc)).returning(ApprovalRequest.id, ApprovalRequest.action))).all()
    if on_resolve:
        for approval_id, action in claimed:
            await on_resolve({"type": "approval_resolved", **resolved_fields(approval_id, "expired", action)})
    return [r[0] for r in claimed]
