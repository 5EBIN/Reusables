import pytest

from app.core.approvals import ApprovalError, TRANSITIONS, check_transition, confirmation, decide


@pytest.mark.parametrize("cur,new", [("pending", "approved"), ("pending", "rejected"), ("approved", "executed"), ("approved", "failed"), ("failed", "approved")])
def test_legal(cur, new):
    check_transition(cur, new)


@pytest.mark.parametrize("cur,new", [("pending", "executed"), ("rejected", "approved"), ("executed", "approved"), ("executed", "failed"), ("pending", "failed"), ("approved", "pending")])
def test_illegal(cur, new):
    with pytest.raises(ApprovalError):
        check_transition(cur, new)


def test_every_status_has_transition_entry():
    from app.core.approvals import STATUSES
    assert set(STATUSES) == set(TRANSITIONS)


def test_two_person_rule_high_risk():
    with pytest.raises(ApprovalError, match="two-person"):
        decide("pending", "u1", "u1", "client_admin", "high", True)
    assert decide("pending", "u1", "u2", "client_admin", "high", True).status == "approved"
    assert decide("pending", "u1", "u1", "client_admin", "low", True).status == "approved"       # low risk: self-approve allowed


@pytest.mark.parametrize("role", ["analyst", "viewer", "employee", "nobody"])
def test_role_gate(role):
    with pytest.raises(ApprovalError):
        decide("pending", "u1", "u2", role, "low", True)


def test_cannot_decide_twice():
    with pytest.raises(ApprovalError):
        decide("approved", "u1", "u2", "client_admin", "low", True)


def test_confirmation_only_from_receipt():
    assert confirmation("send_survey_invites", None) == ""
    assert confirmation("send_survey_invites", {"sent": 2610, "deferred": 0, "skipped": 5, "failed": 1}) == "2,610 sent · 0 deferred · 5 skipped · 1 failed"
    assert "Version 4" in confirmation("publish_survey_version", {"version": 4})
