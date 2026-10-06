"""Single source of 'now' so tests can pin the time, and 'today' is always in the user's timezone."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TZ = "Asia/Kolkata"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TZ)


def user_today(user) -> date:
    """Today's date in the user's own timezone (falls back to Asia/Kolkata)."""
    return utcnow().astimezone(get_zone(user.timezone)).date()
