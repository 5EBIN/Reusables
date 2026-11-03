"""Named periods for "Ask your data". The model names a period; code turns it into dates, in the organisation's time zone, so the model never does date arithmetic."""
from datetime import UTC, date, datetime, timedelta
from typing import Literal, get_args
from zoneinfo import ZoneInfo

from app.core.query_plan import DateRange

Period = Literal["last_7_days", "last_30_days", "this_month", "last_month", "this_quarter", "last_quarter", "this_year", "custom"]
PERIODS: tuple[str, ...] = get_args(Period)
DEFAULT_TZ = "Asia/Dubai"


def today_in(tz: str | None, now: datetime | None = None) -> date:
    """The calendar date right now in the organisation's zone (the default zone when none is set or the name is unknown)."""
    try:
        z = ZoneInfo(tz or DEFAULT_TZ)
    except Exception:                                   # a bad stored name must not break the page
        z = ZoneInfo(DEFAULT_TZ)
    return (now or datetime.now(UTC)).astimezone(z).date()


def _quarter_start(d: date) -> date:
    return date(d.year, 3 * ((d.month - 1) // 3) + 1, 1)


def resolve_period(period: str, today: date) -> DateRange:
    """Inclusive date range of a named period. "Last N days" and the "this ..." periods include today; the "last ..." calendar periods are whole."""
    match period:
        case "last_7_days":
            return DateRange(start=today - timedelta(days=6), end=today)
        case "last_30_days":
            return DateRange(start=today - timedelta(days=29), end=today)
        case "this_month":
            return DateRange(start=today.replace(day=1), end=today)
        case "last_month":
            end = today.replace(day=1) - timedelta(days=1)
            return DateRange(start=end.replace(day=1), end=end)
        case "this_quarter":
            return DateRange(start=_quarter_start(today), end=today)
        case "last_quarter":
            end = _quarter_start(today) - timedelta(days=1)
            return DateRange(start=_quarter_start(end), end=end)
        case "this_year":
            return DateRange(start=date(today.year, 1, 1), end=today)
    raise ValueError(f"not a named period: {period}")
