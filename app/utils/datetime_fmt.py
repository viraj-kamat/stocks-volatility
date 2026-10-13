"""Shared date/time display helpers (ordinal dates, 24h clock, timezone aliases)."""
from datetime import datetime
from zoneinfo import ZoneInfo

# Short names from config.yaml → IANA zones
TZ_ALIASES = {
    "CT": "America/Chicago",
    "CST": "America/Chicago",
    "CDT": "America/Chicago",
    "ET": "America/New_York",
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "PT": "America/Los_Angeles",
    "MT": "America/Denver",
    "UTC": "UTC",
}


def resolve_timezone(name: str) -> ZoneInfo:
    raw = (name or "CT").strip()
    iana = TZ_ALIASES.get(raw.upper(), raw)
    return ZoneInfo(iana)


def _ordinal(day: int) -> str:
    if 11 <= (day % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def _as_datetime(value) -> datetime:
    if value is None:
        raise ValueError("datetime is required")
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if not isinstance(value, datetime):
        value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return value


def to_display_datetime(value, tz_name: str = "CT") -> datetime:
    """
    Convert a timestamp into the configured display timezone.

    - Aware datetimes are converted to the display zone.
    - Naive datetimes are treated as wall-clock in the display zone
      (daily bar dates / trading-day stamps stay on the same calendar day).
    """
    dt = _as_datetime(value)
    target = resolve_timezone(tz_name)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=target)
    return dt.astimezone(target)


def format_date_short(value, tz_name: str = "CT") -> str:
    """27th July '26"""
    local = to_display_datetime(value, tz_name)
    month = local.strftime("%B")
    year = local.strftime("%y")
    return f"{_ordinal(local.day)} {month} '{year}"


def format_datetime_display(value, tz_name: str = "CT") -> str:
    """27th July '26 00:00 hrs (24-hour, no seconds)."""
    local = to_display_datetime(value, tz_name)
    month = local.strftime("%B")
    year = local.strftime("%y")
    return f"{_ordinal(local.day)} {month} '{year} {local.strftime('%H:%M')} hrs"
