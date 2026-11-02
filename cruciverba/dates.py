"""Display SQLite UTC timestamps in the event's local time."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def display_datetime(timestamp):
    try:
        value = datetime.fromisoformat(timestamp)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(ZoneInfo("Europe/Rome")).strftime("%d/%m/%Y alle %H:%M %Z")
    except (TypeError, ValueError):
        return str(timestamp)
