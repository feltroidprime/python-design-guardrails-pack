"""Wall-clock adapter."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Read the wall clock at the outer boundary, always timezone-aware."""
    return datetime.now(tz=UTC)
