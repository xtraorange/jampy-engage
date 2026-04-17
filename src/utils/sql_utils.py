"""Shared SQL helper functions."""

from .constants import ACTIVE_EMPLOYEE_FILTER


def normalize_sql_values(values) -> list[str]:
    """Normalize a scalar-or-list payload to a cleaned list[str]."""
    if values is None:
        return []
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    if isinstance(values, str):
        raw = values.strip()
        return [raw] if raw else []
    raw = str(values).strip()
    return [raw] if raw else []


def single_or_in_condition(column: str, values) -> str:
    """Return SQL equality for one value, or IN (...) for multiple values."""
    normalized = normalize_sql_values(values)
    if not normalized:
        return ""
    if len(normalized) == 1:
        return f"{column} = '{normalized[0]}'"
    csv = ",".join(f"'{value}'" for value in normalized)
    return f"{column} IN ({csv})"


def active_employee_filter(alias: str | None = None) -> str:
    """Return the active-employee predicate with an optional table alias."""
    if not alias:
        return ACTIVE_EMPLOYEE_FILTER
    return ACTIVE_EMPLOYEE_FILTER.replace("status_code", f"{alias}.status_code", 1)