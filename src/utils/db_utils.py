"""Shared helpers for reading common database result shapes."""

from typing import Any


def row_value(row: Any, key: str, fallback_index: int = 0) -> Any:
    """Read a value from a dict or tuple row."""
    if isinstance(row, dict):
        key_lower = key.lower()
        for candidate, value in row.items():
            if str(candidate).lower() == key_lower:
                return value
        return None
    if isinstance(row, (list, tuple)) and len(row) > fallback_index:
        return row[fallback_index]
    return None


def extract_count_value(rows: Any) -> int:
    """Extract an integer count from common DB executor return shapes."""
    if not rows:
        return 0
    first = rows[0]
    if isinstance(first, dict):
        for key in ("COUNT(*)", "CNT", "count", "count(*)", "cnt"):
            if key in first:
                try:
                    return int(first[key])
                except (TypeError, ValueError):
                    return 0
        try:
            return int(next(iter(first.values())))
        except Exception:
            return 0
    try:
        return int(first[0])
    except Exception:
        return 0