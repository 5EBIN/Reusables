from app.core.approvals import RISK, action_subtitle, action_title


def test_every_known_action_has_a_title():
    for a in RISK:
        assert action_title(a) and "_" not in action_title(a)
    assert action_title("brand_new_thing") == "Brand new thing"


def test_subtitles_are_built_from_facts_only():
    assert action_subtitle("send_survey_invites", "Resident Pulse Q4", ["email", "whatsapp"], {}) == "Resident Pulse Q4 · email + WhatsApp"
    assert action_subtitle("publish_survey_version", "Maintenance CSAT", None, {"version": 5}) == "Maintenance CSAT v5"
    assert action_subtitle("start_conversations", "S", None, {"channel": "sms"}) == "S · SMS"
    assert action_subtitle("launch_360_cycle", None, None, {}) == ""
    assert action_subtitle("send_reminder", "استبيان", ["email"], None) == "استبيان · email"
