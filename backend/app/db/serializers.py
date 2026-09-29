"""
Data Serialization and Adapter Utilities for Portable Database Support (Step 4).
Ensures safe conversion between SQLite text representations and PostgreSQL JSONB / TIMESTAMPTZ types.
"""
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union


def ensure_json_str(val: Any, default: str = "{}") -> str:
    """
    Ensure value is a serialized JSON string.
    Works whether input is a Python dict/list, None, or an existing JSON string.
    """
    if val is None:
        return default
    if isinstance(val, (dict, list)):
        return json.dumps(val)
    if isinstance(val, str):
        val_str = val.strip()
        if not val_str:
            return default
        return val_str
    return json.dumps(val)


def ensure_json_obj(val: Any, default: Optional[Any] = None) -> Any:
    """
    Ensure value is a deserialized Python dict or list.
    Safe against both PostgreSQL JSONB (already dict/list) and SQLite TEXT (needs json.loads).
    """
    if default is None:
        default = {}
    if val is None:
        return default
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        val_str = val.strip()
        if not val_str:
            return default
        try:
            return json.loads(val_str)
        except (json.JSONDecodeError, TypeError):
            return default
    return default


def format_utc_iso(dt: Optional[Union[datetime, str]]) -> Optional[str]:
    """
    Format a datetime object as a standardized ISO-8601 UTC timestamp string with 'Z'.
    Guarantees unambiguous TIMESTAMPTZ parsing in PostgreSQL.
    """
    if dt is None:
        return None
    if isinstance(dt, str):
        # Already string, check if timezone is missing
        if not dt.endswith("Z") and not ("+" in dt[10:] or "-" in dt[10:]):
            return f"{dt}Z"
        return dt
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat()
    return None


def parse_utc_datetime(val: Optional[Union[datetime, str]]) -> Optional[datetime]:
    """
    Parse a timestamp string or datetime object into a timezone-aware UTC datetime.
    """
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    if isinstance(val, str):
        clean_str = val.strip()
        if not clean_str:
            return None
        # Handle trailing Z
        if clean_str.endswith("Z"):
            clean_str = clean_str[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(clean_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt
        except ValueError:
            return None
    return None
