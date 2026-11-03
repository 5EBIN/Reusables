from datetime import datetime, time, UTC

import pytest

from app.core.distribution import (
    mask_phone, neutralize, next_allowed, normalize_email, normalize_phone, parse_csv, presend_checks, render_template, validate_template,
)


@pytest.mark.parametrize("raw,out", [
    ("0555550148", "+971555550148"), ("+971 55 555 0148", "+971555550148"), ("00971555550148", "+971555550148"), ("971555550148", "+971555550148"),
    ("٠٥٥٥٥٥٠١٤٨", "+971555550148"), ("(055) 555-0148", "+971555550148"), ("+44 7700 900123", "+447700900123"),
    ("", None), ("abc", None), ("123", None), ("+1234567890123456789", None), ("0", None), (None, None),
])
def test_normalize_phone(raw, out):
    assert normalize_phone(raw)[0] == out


@pytest.mark.parametrize("raw,out", [("user@example.com", "user@example.com"), (" user@example.com ", "user@example.com"), ("no", None), ("a@b", None), ("", None), (None, None), ("a user@example.com", None)])
def test_normalize_email(raw, out):
    assert normalize_email(raw) == out


def test_mask_phone():
    assert mask_phone("+971555550148") == "+971 55 ••• 0148" and mask_phone(None) is None


CSV = "﻿Full Name,E-mail,Mobile,Lang,Block\nعمر الصديقي,user@example.com,0555550148,UR,B4\nJordan,user@example.com,,ar,A1\nDup,user@example.com,0501111111,en,C\nBad,notanemail,,en,X\n"
MAP = {"Full Name": "name", "E-mail": "email", "Mobile": "phone", "Lang": "language", "Block": "attribute:building"}


def test_csv_import_bom_arabic_dedupe_and_report():
    r = parse_csv(CSV, MAP)
    assert r.bom and len(r.rows) == 2 and r.duplicates == 1 and len(r.errors) == 1
    assert r.rows[0]["name"] == "عمر الصديقي" and r.rows[0]["email"] == "user@example.com" and r.rows[0]["phone"] == "+971555550148"
    assert r.rows[0]["attributes"] == {"building": "B4"} and r.rows[0]["language"] == "ur"
    assert {c["column"]: c["status"] for c in r.columns}["Mobile"] == "Normalised"


@pytest.mark.parametrize("mapping", [{"Nope": "email"}, {"E-mail": "bogus"}, {"E-mail": "attribute:Bad Key"}, {"E-mail": "attribute:"}])
def test_csv_mapping_rejections(mapping):
    with pytest.raises(ValueError):
        parse_csv(CSV, mapping)


def test_csv_large_import_performance():
    rows = "\n".join(f"U{i},u{i}@example.ae,05{i % 10}{1000000 + i}" for i in range(10_000))
    r = parse_csv("name,email,phone\n" + rows, {"name": "name", "email": "email", "phone": "phone"})
    assert len(r.rows) == 10_000


@pytest.mark.parametrize("cell,out", [("=1+1", "'=1+1"), ("+5", "'+5"), ("-5", "'-5"), ("@SUM(A1)", "'@SUM(A1)"), ("\tx", "'\tx"), ("normal", "normal"), ("", "")])
def test_neutralize(cell, out):
    assert neutralize(cell) == out


@pytest.mark.parametrize("t", ["Hello {first_name} {link}", "{name}", "plain"])
def test_template_ok(t):
    validate_template(t)


@pytest.mark.parametrize("t", ["{password}", "{first_name} {__class__}", "{secret_token}", "{{x}}"])
def test_template_unknown_vars_rejected(t):
    with pytest.raises(ValueError):
        validate_template(t)


@pytest.mark.parametrize("t", ["{LINK}", "{a.b}", "{0}"])
def test_template_inert_text_is_not_a_variable(t):
    assert "password" not in render_template(t, {})


def test_render():
    assert render_template("Hi {first_name}, {link}", {"first_name": "Jordan", "link": "https://x"}) == "Hi Jordan, https://x"


def C(i, email=None, phone=None):
    return {"id": i, "email": email, "phone": phone}


def test_presend_checks_counts_like_the_mockup():
    contacts = [C(1, "user@example.com", "+971500000001"), C(2, "user@example.com", "+971500000002"), C(3, "user@example.com", None), C(4, "user@example.com", "+971500000004"), C(5, "user@example.com", "+971500000005")]
    consents = {(i, ch): "opt_in" for i in (1, 2, 3, 5) for ch in ("email", "whatsapp")}
    consents[(4, "email")] = "opt_out"
    supp = {("email", "user@example.com"), ("whatsapp", "+971500000002")}
    aud, plan = presend_checks(contacts, ["email", "whatsapp"], consents, supp, {5})
    assert aud.selected == 5 and aud.suppressed == 1 and aud.no_consent == 1 and aud.recently_contacted == 1
    assert aud.will_receive == 2 and aud.per_channel == {"email": 2, "whatsapp": 1}
    reasons = {(c, ch): r for c, ch, r in plan}
    assert reasons[(3, "whatsapp")] == "no_address" and reasons[(2, "email")] == "suppressed" and reasons[(4, "email")] == "no_consent"


def test_unknown_consent_is_not_consent():
    aud, _ = presend_checks([C(1, "user@example.com")], ["email"], {}, set(), set())
    assert aud.will_receive == 0 and aud.no_consent == 1


@pytest.mark.parametrize("now_utc,expected_local_hour", [
    (datetime(2026, 10, 7, 18, 0, tzinfo=UTC), None),        # 22:00 Dubai -> deferred to 08:00 next day
    (datetime(2026, 10, 7, 3, 0, tzinfo=UTC), None),         # 07:00 Dubai -> deferred to 08:00 same day
    (datetime(2026, 10, 7, 6, 0, tzinfo=UTC), "same"),       # 10:00 Dubai -> allowed
])
def test_quiet_hours(now_utc, expected_local_hour):
    out = next_allowed(now_utc, "Asia/Dubai", time(21, 0), time(8, 0))
    if expected_local_hour == "same":
        assert out == now_utc
    else:
        assert out > now_utc and (out.hour + 4) % 24 == 8 and out.minute == 0


def test_quiet_hours_non_wrapping_window():
    now = datetime(2026, 10, 7, 10, 0, tzinfo=UTC)   # 14:00 Dubai, window 13:00-15:00
    out = next_allowed(now, "Asia/Dubai", time(13, 0), time(15, 0))
    assert (out.hour + 4) % 24 == 15
