"""The ONLY module allowed to import app.app.executors. Executes an approved action exactly once and records a receipt."""
import json
import uuid

from app.adapters.queue_pg import PgQueue
from app.core.approvals import ApprovalError, NotApprovedError, check_transition
from app.db.repos import approvals as repo


def _executor(action_type: str):
    from app.app.executors import case_followup, launch_360, publish, send_invites, start_conversations     # imported here: nothing else may import executors
    return {"send_survey_invites": send_invites, "send_reminder": send_invites, "publish_survey_version": publish,
            "launch_360_cycle": launch_360, "send_case_followup": case_followup, "start_conversations": start_conversations}.get(action_type)


def _record(a) -> dict:
    """The approval as the executors read it: a dict with the payload decoded."""
    return a.model_dump() | {"payload": json.loads(a.payload)}


async def run_approved(conn, approval_id: uuid.UUID, notifier, base_url: str = "http://localhost:3000", now=None) -> dict:
    a = await repo.get_for_update(conn, approval_id)
    if a is None:
        raise ApprovalError("not found")
    if a.status == "executed":
        return json.loads(a.receipt)                     # idempotent
    if a.status != "approved":
        raise NotApprovedError(f"approval is {a.status}")
    mod = _executor(a.action_type)
    if mod is None:
        raise ApprovalError("no executor for action type")
    try:
        receipt = await mod.execute(conn, notifier, _record(a), base_url, now)
    except Exception as e:
        check_transition("approved", "failed")
        await repo.mark_failed(conn, approval_id, str(e)[:500])
        await repo.log_system_event(conn, a.org_id, approval_id, "failed", json.dumps({"error": str(e)[:300]}))
        raise
    check_transition("approved", "executed")
    await repo.mark_executed(conn, approval_id, json.dumps(receipt))
    if receipt.get("next_release"):
        from datetime import datetime
        await PgQueue().enqueue(conn, "release_deferred", {"approval_id": str(approval_id)}, run_after=datetime.fromisoformat(receipt["next_release"]))
    await repo.log_system_event(conn, a.org_id, approval_id, "executed", json.dumps(receipt))
    return receipt


async def release_deferred(conn, approval_id: uuid.UUID, notifier, base_url: str, now=None) -> dict:
    """Second pass for deliveries deferred by quiet hours. Replay-safe: already sent deliveries are skipped."""
    a = await repo.get_for_update(conn, approval_id)
    if a is None or a.status != "executed":
        raise NotApprovedError("not executed")
    mod = _executor(a.action_type)
    receipt = await mod.execute(conn, notifier, _record(a), base_url, now)
    await repo.set_receipt(conn, approval_id, json.dumps(receipt))
    if receipt.get("next_release"):
        from datetime import datetime
        await PgQueue().enqueue(conn, "release_deferred", {"approval_id": str(approval_id)}, run_after=datetime.fromisoformat(receipt["next_release"]))
    return receipt


async def send_360_reminders(conn, cycle_id: uuid.UUID, day_offset: int, notifier, base_url: str, now=None) -> dict:
    from app.app.executors import launch_360
    return await launch_360.remind(conn, notifier, cycle_id, day_offset, base_url, now)
