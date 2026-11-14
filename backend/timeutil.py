"""Timestamps are stored in UTC; reports and displays use Puerto Rico time."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

PR_TZ = ZoneInfo("America/Puerto_Rico")


def to_pr(dt: datetime) -> datetime:
    """Convert a naive-UTC datetime (as stored) to Puerto Rico local time."""
    return dt.replace(tzinfo=timezone.utc).astimezone(PR_TZ)


def pr_date(dt: datetime) -> str:
    return to_pr(dt).date().isoformat() if dt else None


def pr_midnight_utc(date_str: str) -> datetime:
    """Start of a Puerto Rico calendar day (YYYY-MM-DD), as naive UTC for querying."""
    local = datetime.fromisoformat(date_str).replace(tzinfo=PR_TZ)
    return local.astimezone(timezone.utc).replace(tzinfo=None)
