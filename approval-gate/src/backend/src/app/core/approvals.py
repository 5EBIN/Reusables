"""Approval gate state machine. Pure; DB access lives in app/. Confirmations are rendered from receipts only."""
from dataclasses import dataclass

STATUSES = ("pending", "approved", "rejected", "executed", "failed")
TRANSITIONS = {
    "pending": {"approved", "rejected"},
    "approved": {"executed", "failed"},
    "failed": {"approved"},          # retry after a human re-approves
    "rejected": set(),
    "executed": set(),
}
RISK = {
    "send_survey_invites": "high", "send_reminder": "medium", "publish_survey_version": "low",
    "publish_benchmark_rows": "high", "release_360_report": "high", "launch_360_cycle": "high", "approve_payout": "high", "send_case_followup": "high", "start_conversations": "high",
}
APPROVER_ROLES = {"client_admin", "consultant", "super_admin"}


class ApprovalError(Exception):
    pass


class NotApprovedError(ApprovalError):
    pass


def check_transition(cur: str, new: str) -> None:
    if new not in TRANSITIONS.get(cur, set()):
        raise ApprovalError(f"illegal transition {cur} -> {new}")


@dataclass
class Decision:
    status: str


def decide(status: str, proposer: str | None, approver: str, approver_role: str, risk: str, approve: bool) -> Decision:
    if status != "pending":
        raise ApprovalError("already decided")
    if approver_role not in APPROVER_ROLES:
        raise ApprovalError("role cannot approve")
    if risk == "high" and proposer is not None and proposer == approver:
        raise ApprovalError("two-person rule: approver cannot be the proposer for high-risk actions")
    new = "approved" if approve else "rejected"
    check_transition(status, new)
    return Decision(new)


def confirmation(action_type: str, receipt: dict | None) -> str:
    """User-visible confirmation text rendered ONLY from the execution receipt (never from model text)."""
    if not receipt:
        return ""
    if action_type in ("send_survey_invites", "send_reminder"):
        return (f"{receipt.get('sent', 0):,} sent · {receipt.get('deferred', 0):,} deferred · {receipt.get('skipped', 0):,} skipped"
                f" · {receipt.get('failed', 0):,} failed")
    if action_type == "publish_survey_version":
        return f"Version {receipt.get('version')} published"
    return ", ".join(f"{k}: {v}" for k, v in sorted(receipt.items()))


ACTION_TITLES = {
    "send_survey_invites": "Send invitations", "send_reminder": "Send reminder", "publish_survey_version": "Publish survey version", "publish_benchmark_rows": "Publish benchmark rows",
    "release_360_report": "Release 360 report", "launch_360_cycle": "Launch 360 cycle", "approve_payout": "Approve payout", "send_case_followup": "Send case follow-up",
    "start_conversations": "Start conversations",
}
CHANNEL_NAMES = {"email": "email", "sms": "SMS", "whatsapp": "WhatsApp", "qr": "QR", "link": "link", "kiosk": "kiosk"}


def action_title(action_type: str) -> str:
    return ACTION_TITLES.get(action_type) or action_type.replace("_", " ").capitalize()


def action_subtitle(action_type: str, survey_title: str | None, channels: list[str] | None, payload: dict | None) -> str:
    """One line under the action name: 'Resident Pulse Q4 · email + WhatsApp'. Built from stored facts only."""
    parts: list[str] = []
    if survey_title:
        parts.append(survey_title + (f" v{payload['version']}" if action_type == "publish_survey_version" and payload and payload.get("version") else ""))
    chans = channels or ([payload["channel"]] if payload and payload.get("channel") else [])
    if chans:
        parts.append(" + ".join(CHANNEL_NAMES.get(ch, ch) for ch in chans))
    return " · ".join(parts)
