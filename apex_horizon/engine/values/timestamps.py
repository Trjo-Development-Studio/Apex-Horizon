"""Real-world timestamps.

Design Bible V30.5 requires timestamps stored for save metadata — save creation
date and last save date (V16.16) — to use a standard, unambiguous real-world
date format, kept entirely distinct from the in-game day counter defined in
V30.4, so that real-world save history and simulation time are never confused.

ISO 8601 in UTC is used throughout: it sorts correctly as text, carries an
explicit offset, and is unambiguous across locales.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """The current real-world time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def to_iso(moment: datetime) -> str:
    """Format a datetime as an ISO 8601 UTC string.

    Naive datetimes are assumed to be UTC rather than rejected, so a timestamp
    read from an older save can never prevent that save from loading (V16.15).
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).isoformat(timespec="seconds")


def now_iso() -> str:
    """The current real-world time as an ISO 8601 UTC string."""
    return to_iso(utc_now())


def parse_iso(text: str) -> datetime:
    """Parse an ISO 8601 timestamp, returning a timezone-aware UTC datetime."""
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)
