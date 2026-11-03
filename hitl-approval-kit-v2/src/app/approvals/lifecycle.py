"""Approval requests: create (idempotent per grouping key) -> pending -> resolved by status, or expired by TTL.

Extracted pieces: resolved_fields, await_approval_decision and get_pending_approvals. The rest of the lifecycle is in resolve.py.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app._stubs import ApprovalRequest

logger = logging.getLogger(__name__)

EventEmitter = Callable[[dict[str, Any]], Awaitable[None]]
def resolved_fields(approval_id: str, status: str, action: str) -> dict:
    """The decision fields of an approval_resolved SSE event (the caller adds "type": "approval_resolved" and any extras). `approved` is true only when status == "approved": a client
    must decide from it (or from status), never from a missing field. Rejected, expired and declined are all approved False."""
    return {"approval_id": approval_id, "status": status, "approved": status == "approved", "action": action}
async def await_approval_decision(approval_id: str, timeout_s: int = 86400) -> dict:
    """Poll the database until the approval leaves 'pending', or until timeout_s expires.

    Turns an HTTP POST (a person clicking Approve/Reject) into something a suspended background task can wait on, without an in-memory registry that would not survive a restart.
    The default timeout is 24 hours: approvals sit in a human's queue. Returns {"approved": bool, "status", "notes", "feedback"} or {"timeout": True}.
    """
    from app._stubs import AsyncSessionLocal

    deadline = datetime.now(timezone.utc) + timedelta(seconds=timeout_s)
    while datetime.now(timezone.utc) < deadline:
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))
            approval = res.scalar_one_or_none()
            if approval and approval.status != "pending":
                return {
                    "approved": approval.status == "approved",
                    "status": approval.status,
                    "notes": approval.notes or "",
                    "feedback": approval.feedback or "",
                }
        await asyncio.sleep(2)

    logger.warning("[approval] await_approval_decision timed out for %s", approval_id)
    return {"timeout": True}


async def get_pending_approvals(project_id: str, db: AsyncSession) -> list[ApprovalRequest]:
    result = await db.execute(
        select(ApprovalRequest).where(
            ApprovalRequest.project_id == project_id,
            ApprovalRequest.status == "pending",
        ).order_by(ApprovalRequest.created_at)
    )
    return result.scalars().all()
