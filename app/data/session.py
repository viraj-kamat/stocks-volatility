"""US equity trading session helper (24-hour market)."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def current_session(now: datetime | None = None) -> str:
    """overnight | pre | regular | post | closed (weekend), in ET."""
    now = (now or datetime.now(NY)).astimezone(NY)
    wd, minutes = now.weekday(), now.hour * 60 + now.minute

    # Overnight (Blue Ocean / Alpaca): Sun 8pm ET -> Fri 8pm ET, 8pm-4am nightly
    if wd == 5 or (wd == 6 and minutes < 20 * 60) or (wd == 4 and minutes >= 20 * 60):
        return "closed"
    if minutes >= 20 * 60 or minutes < 4 * 60:
        return "overnight"
    if minutes < 9 * 60 + 30:
        return "pre"
    if minutes < 16 * 60:
        return "regular"
    return "post"
