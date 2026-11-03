from datetime import UTC, datetime, time


from app.core.schedule import next_run, sign, verify

T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)   # Wednesday


def test_daily_after_and_before():
    assert next_run("daily", time(8), "Asia/Dubai", T0) == datetime(2026, 10, 8, 4, 0, tzinfo=UTC)
    assert next_run("daily", time(17), "Asia/Dubai", T0) == datetime(2026, 10, 7, 13, 0, tzinfo=UTC)


def test_weekly_monday():
    assert next_run("weekly", time(8), "UTC", T0, dow=0).date().isoformat() == "2026-10-12"


def test_monthly_clamped_and_strictly_after():
    assert next_run("monthly", time(8), "UTC", T0, dom=31).date().isoformat() == "2026-10-28"
    assert next_run("monthly", time(8), "UTC", datetime(2026, 10, 28, 8, 0, tzinfo=UTC), dom=28).date().isoformat() == "2026-11-28"


def test_token_roundtrip_and_rejections():
    t = sign("s" * 32, "o", "j", 100)
    assert verify("s" * 32, t, 50) == ("o", "j")
    for bad in (verify("s" * 32, t, 100), verify("x" * 32, t, 50), verify("s" * 32, t[:-3], 50), verify("s" * 32, "", 50), verify("s" * 32, "!!", 50), verify("s" * 32, t.swapcase(), 50)):
        assert bad is None
