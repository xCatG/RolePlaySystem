"""
Time utilities for consistent datetime handling across the application.

All functions work with UTC timezone-aware datetimes only.
"""

from datetime import datetime, timezone
from typing import Optional


def utc_now() -> datetime:
    """Return a timezone-aware datetime in UTC."""
    return datetime.now(timezone.utc)


def utc_now_isoformat(zulu: bool = True, microseconds: bool = True) -> str:
    """
    Return current UTC time as ISO 8601 string.

    Args:
        zulu: If True, return with 'Z' suffix. If False, keep '+00:00'.
        microseconds: If False, omit microsecond precision.

    Returns:
        ISO 8601 formatted UTC string.
    """
    now = utc_now()
    if not microseconds:
        now = now.replace(microsecond=0)

    iso_str = now.isoformat()
    if zulu:
        if iso_str.endswith("+00:00"):
            iso_str = iso_str[:-6] + "Z"
    return iso_str


def parse_utc_datetime(dt_str: str) -> datetime:
    """
    Parse an ISO 8601 UTC string into a timezone-aware datetime object.

    Supports both 'Z' and '+00:00' suffixes.

    Raises:
        ValueError if the string cannot be parsed or is not UTC.
    """
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1] + "+00:00"
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo != timezone.utc:
        raise ValueError("Only UTC datetime strings are supported.")
    return dt


def is_valid_utc_isoformat(dt_str: str) -> bool:
    """
    Return True if the string is a valid UTC ISO 8601 datetime.
    """
    try:
        _ = parse_utc_datetime(dt_str)
        return True
    except Exception:
        return False