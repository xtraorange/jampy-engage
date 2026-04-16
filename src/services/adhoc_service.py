"""Shared helpers for ad hoc UI workflows."""

import csv
import io
import re
from typing import Any, Dict, Iterable, List, Sequence

from ..db import DatabaseExecutor
from .employee_lookup_service import EXPORTABLE_FIELDS


DEFAULT_EMPLOYEE_COLUMNS: List[str] = [
    "EMPLOYEE_ID",
    "FIRST_NAME",
    "LAST_NAME",
    "USERNAME",
    "EMAIL",
    "JOB_CODE",
    "JOB_TITLE",
    "DEPARTMENT_ID",
    "LOCATION",
    "BU_CODE",
    "COMPANY",
    "TREE_BRANCH",
    "FULL_PART_TIME",
    "STATUS_CODE",
]

_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_LABEL_OVERRIDES: Dict[str, str] = {
    "EMPLOYEE_ID": "Employee ID",
    "FIRST_NAME": "First Name",
    "LAST_NAME": "Last Name",
    "USERNAME": "Username",
    "EMAIL": "Email",
    "JOB_CODE": "Job Code",
    "JOB_TITLE": "Job Title",
    "DEPARTMENT_ID": "Department ID",
    "LOCATION": "Location",
    "BU_CODE": "Business Unit",
    "COMPANY": "Company",
    "TREE_BRANCH": "Tree Branch",
    "FULL_PART_TIME": "Full/Part Time",
    "STATUS_CODE": "Status Code",
}


def label_for_column(column_name: str) -> str:
    """Return a user-facing label for a database column."""
    column = str(column_name or "").strip().upper()
    if column in _LABEL_OVERRIDES:
        return _LABEL_OVERRIDES[column]
    return column.replace("_", " ").title()


def normalize_column_name(value: Any) -> str:
    """Normalize a candidate SQL identifier and reject unsafe values."""
    candidate = str(value or "").strip().upper()
    if not candidate or not _SAFE_IDENTIFIER_RE.match(candidate):
        return ""
    return candidate


def parse_allowed_columns(columns: Iterable[Any]) -> List[str]:
    """Normalize and deduplicate a list of allowed column names."""
    seen = set()
    normalized = []
    for value in columns or []:
        column = normalize_column_name(value)
        if not column or column in seen:
            continue
        seen.add(column)
        normalized.append(column)
    return normalized


def load_employee_mv_columns(oracle_tns: str) -> List[str]:
    """Load available omsadm.employee_mv columns, with a safe fallback."""
    executor = DatabaseExecutor(oracle_tns)
    try:
        rows = executor.run_query(
            """
            SELECT COLUMN_NAME
            FROM ALL_TAB_COLUMNS
            WHERE OWNER = 'OMSADM'
              AND TABLE_NAME = 'EMPLOYEE_MV'
            ORDER BY COLUMN_ID
            """
        )
        columns = []
        for row in rows:
            value = row_value(row, "COLUMN_NAME", 0)
            column = normalize_column_name(value)
            if column and column not in columns:
                columns.append(column)
        return columns or list(DEFAULT_EMPLOYEE_COLUMNS)
    except Exception:
        return list(DEFAULT_EMPLOYEE_COLUMNS)
    finally:
        executor.close()


def _escape_sql_literal(value: Any) -> str:
    return str(value or "").replace("'", "''").strip()


def _build_filter_condition(column: str, operator: str, value: Any) -> str:
    op = str(operator or "equals").strip().lower()
    text_value = _escape_sql_literal(value)

    if op == "is_null":
        return f"{column} IS NULL"
    if op == "is_not_null":
        return f"{column} IS NOT NULL"
    if not text_value:
        return ""
    if op == "equals":
        return f"UPPER({column}) = UPPER('{text_value}')"
    if op == "not_equals":
        return f"UPPER({column}) <> UPPER('{text_value}')"
    if op == "contains":
        return f"UPPER({column}) LIKE UPPER('%{text_value}%')"
    if op == "starts_with":
        return f"UPPER({column}) LIKE UPPER('{text_value}%')"
    if op == "ends_with":
        return f"UPPER({column}) LIKE UPPER('%{text_value}')"
    if op == "in_list":
        values = [
            _escape_sql_literal(item)
            for item in re.split(r"[\r\n,]+", str(value or ""))
            if _escape_sql_literal(item)
        ]
        if not values:
            return ""
        if len(values) == 1:
            return f"UPPER({column}) = UPPER('{values[0]}')"
        csv_values = ", ".join(f"UPPER('{item}')" for item in values)
        return f"UPPER({column}) IN ({csv_values})"
    raise ValueError(f"Unsupported filter operator: {operator}")


def build_custom_employee_sql(
    selected_columns: Sequence[Any],
    filters: Sequence[Dict[str, Any]],
    allowed_columns: Sequence[Any],
) -> str:
    """Build a validated SELECT query against omsadm.employee_mv."""
    normalized_allowed = parse_allowed_columns(allowed_columns)
    allowed_set = set(normalized_allowed)

    chosen_columns = []
    for value in selected_columns or []:
        column = normalize_column_name(value)
        if column and column in allowed_set and column not in chosen_columns:
            chosen_columns.append(column)

    if not chosen_columns:
        raise ValueError("Select at least one output column.")

    conditions = ["status_code != 'T'"]
    for item in filters or []:
        column = normalize_column_name((item or {}).get("column"))
        if not column:
            continue
        if column not in allowed_set:
            raise ValueError(f"Unsupported filter column: {column}")
        clause = _build_filter_condition(column, (item or {}).get("operator"), (item or {}).get("value"))
        if clause:
            conditions.append(clause)

    order_parts = [part for part in ("LAST_NAME", "FIRST_NAME", "EMPLOYEE_ID") if part in allowed_set]
    order_sql = f" ORDER BY {', '.join(order_parts)}" if order_parts else ""
    return (
        f"SELECT {', '.join(chosen_columns)} "
        f"FROM omsadm.employee_mv "
        f"WHERE {' AND '.join(conditions)}"
        f"{order_sql}"
    )


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


def build_csv_buffer(headers: Sequence[Any], rows: Sequence[Sequence[Any]]) -> io.BytesIO:
    """Return a UTF-8 CSV file buffer."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(list(headers or []))
    for row in rows or []:
        writer.writerow(list(row or []))

    buffer = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    buffer.seek(0)
    return buffer


def people_rows_from_selection(selected_people: Sequence[Dict[str, Any]]) -> List[List[Any]]:
    """Flatten selected person payloads into CSV row values."""
    ordered_fields = [field for field in EXPORTABLE_FIELDS if field != "match_method"]
    rows: List[List[Any]] = []
    for person in selected_people or []:
        row = []
        for field in ordered_fields:
            if field == "employee_id":
                row.append(person.get("employee_id") or person.get("id", ""))
            else:
                row.append(person.get(field, ""))
        rows.append(row)
    return rows


def people_csv_buffer(selected_people: Sequence[Dict[str, Any]]) -> io.BytesIO:
    """Build a CSV export for selected people."""
    ordered_fields = [field for field in EXPORTABLE_FIELDS if field != "match_method"]
    headers = [EXPORTABLE_FIELDS[field] for field in ordered_fields]
    return build_csv_buffer(headers, people_rows_from_selection(selected_people))


def objectid_rows_from_query_rows(rows: Sequence[Any]) -> List[List[str]]:
    """Convert query results into ObjectId report rows like standard report generation."""
    output_rows: List[List[str]] = []
    for row in rows or []:
        username = row_value(row, "USERNAME", 0)
        if username is None:
            continue
        object_id = str(username).strip()
        if not object_id:
            continue
        if "@" not in object_id:
            object_id = f"{object_id}@fastenal.com"
        output_rows.append([object_id])
    return output_rows