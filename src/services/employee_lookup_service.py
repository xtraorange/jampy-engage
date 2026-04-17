"""Helpers for searching employee records for UI workflows."""

from typing import Any, Dict, List, Optional

from ..db import DatabaseExecutor
from ..utils import ACTIVE_EMPLOYEE_FILTER, ADVANCED_SEARCH_COLUMNS, EXPORTABLE_FIELDS, serialize_employee_row


def _sanitize(value: Optional[str]) -> str:
    return (value or "").replace("'", "''").strip()


def _cache_key(query: Optional[str], first_name: Optional[str], last_name: Optional[str]) -> tuple[str, str, str]:
    return (
        (query or "").strip().lower(),
        (first_name or "").strip().lower(),
        (last_name or "").strip().lower(),
    )


def _non_empty(value: Optional[str]) -> bool:
    return bool(str(value or "").strip())


EMPLOYEE_SEARCH_SELECT = """
SELECT EMPLOYEE_ID,
       FIRST_NAME,
       LAST_NAME,
       USERNAME,
       EMAIL,
       JOB_TITLE,
       DEPARTMENT_ID,
       LOCATION,
       BU_CODE,
       COMPANY,
       TREE_BRANCH,
       FULL_PART_TIME,
       JOB_CODE
FROM omsadm.employee_mv
""".strip()


class EmployeeLookupService:
    """Search employee records using the configured database."""

    def __init__(self, oracle_tns: str):
        self.oracle_tns = oracle_tns

    def _build_search_sql(self, conditions_sql: str, limit: Optional[int] = None) -> str:
        limit_clause = f"\nFETCH FIRST {max(1, int(limit))} ROWS ONLY" if limit is not None else ""
        return f"""
        {EMPLOYEE_SEARCH_SELECT}
        WHERE {ACTIVE_EMPLOYEE_FILTER}
          AND ({conditions_sql})
        ORDER BY FIRST_NAME, LAST_NAME, USERNAME{limit_clause}
        """

    def _run_search(self, conditions_sql: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        executor = DatabaseExecutor(self.oracle_tns)
        try:
            return [
                serialize_employee_row(row)
                for row in executor.run_query(self._build_search_sql(conditions_sql, limit))
            ]
        finally:
            executor.close()

    def search_candidates_batch(
        self,
        inputs: List[Dict[str, Optional[str]]],
        limit: int = 20,
        chunk_size: int = 200,
    ) -> Dict[tuple[str, str, str], List[Dict[str, Any]]]:
        grouped_keys: Dict[tuple[str, str], List[tuple[str, str, str]]] = {}
        results: Dict[tuple[str, str, str], List[Dict[str, Any]]] = {}

        for item in inputs:
            query = item.get("query") or item.get("display") or ""
            first = _sanitize(item.get("first_name"))
            last = _sanitize(item.get("last_name"))
            cache_key = _cache_key(query, first, last)
            if cache_key in results:
                continue
            results[cache_key] = []
            if not first or not last:
                continue
            grouped_keys.setdefault((first.lower(), last.lower()), []).append(cache_key)

        exact_pairs = list(grouped_keys.keys())
        if not exact_pairs:
            return results

        executor = DatabaseExecutor(self.oracle_tns)
        try:
            for start in range(0, len(exact_pairs), max(1, int(chunk_size))):
                chunk = exact_pairs[start:start + max(1, int(chunk_size))]
                conditions = [
                    f"(UPPER(FIRST_NAME) = UPPER('{first}') AND UPPER(LAST_NAME) = UPPER('{last}'))"
                    for first, last in chunk
                ]
                rows = executor.run_query(self._build_search_sql(" OR ".join(conditions)))
                serialized = [serialize_employee_row(row) for row in rows]
                by_pair: Dict[tuple[str, str], List[Dict[str, Any]]] = {}
                for item in serialized:
                    pair_key = (
                        str(item.get("first_name") or "").strip().lower(),
                        str(item.get("last_name") or "").strip().lower(),
                    )
                    by_pair.setdefault(pair_key, []).append(item)
                for pair_key in chunk:
                    matches = by_pair.get(pair_key, [])[:max(1, int(limit))]
                    for cache_key in grouped_keys.get(pair_key, []):
                        results[cache_key] = matches
        finally:
            executor.close()

        return results

    def search_candidates_exact(
        self,
        query: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        search = _sanitize(query)
        first = _sanitize(first_name)
        last = _sanitize(last_name)

        if not search and not first and not last:
            return []

        conditions = []
        if first and last:
            conditions.append(
                f"(UPPER(FIRST_NAME) = UPPER('{first}') AND UPPER(LAST_NAME) = UPPER('{last}'))"
            )
        elif search:
            conditions.extend([
                f"UPPER(FIRST_NAME || ' ' || LAST_NAME) = UPPER('{search}')",
                f"UPPER(USERNAME) = UPPER('{search}')",
                f"UPPER(EMAIL) = UPPER('{search}')",
                f"UPPER(EMPLOYEE_ID) = UPPER('{search}')",
            ])
            if first:
                conditions.append(f"UPPER(FIRST_NAME) = UPPER('{first}')")
            if last:
                conditions.append(f"UPPER(LAST_NAME) = UPPER('{last}')")
        else:
            if first:
                conditions.append(f"UPPER(FIRST_NAME) = UPPER('{first}')")
            if last:
                conditions.append(f"UPPER(LAST_NAME) = UPPER('{last}')")

        return self._run_search(" OR ".join(conditions), limit)

    def search_candidates(
        self,
        query: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        search = _sanitize(query)
        first = _sanitize(first_name)
        last = _sanitize(last_name)

        if not search and not first and not last:
            return []

        conditions = []
        if search:
            conditions.extend([
                f"UPPER(EMPLOYEE_ID) LIKE UPPER('%{search}%')",
                f"UPPER(FIRST_NAME) LIKE UPPER('%{search}%')",
                f"UPPER(LAST_NAME) LIKE UPPER('%{search}%')",
                f"UPPER(USERNAME) LIKE UPPER('%{search}%')",
                f"UPPER(EMAIL) LIKE UPPER('%{search}%')",
                f"UPPER(FIRST_NAME || ' ' || LAST_NAME) LIKE UPPER('%{search}%')",
            ])

        if first and last:
            conditions.append(
                f"(UPPER(FIRST_NAME) LIKE UPPER('%{first}%') AND UPPER(LAST_NAME) LIKE UPPER('%{last}%'))"
            )
        elif first:
            conditions.append(f"UPPER(FIRST_NAME) LIKE UPPER('%{first}%')")
        elif last:
            conditions.append(f"UPPER(LAST_NAME) LIKE UPPER('%{last}%')")

        return self._run_search(" OR ".join(conditions), limit)

    def search_candidates_basic(
        self,
        query: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Typeahead search restricted to name and username for consistent people-pickers."""
        search = _sanitize(query)
        if not search:
            return []

        conditions = [
            f"UPPER(FIRST_NAME) LIKE UPPER('%{search}%')",
            f"UPPER(LAST_NAME) LIKE UPPER('%{search}%')",
            f"UPPER(FIRST_NAME || ' ' || LAST_NAME) LIKE UPPER('%{search}%')",
            f"UPPER(USERNAME) LIKE UPPER('%{search}%')",
        ]
        return self._run_search(" OR ".join(conditions), limit)

    def search_candidates_advanced(
        self,
        filters: Dict[str, Optional[str]],
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Advanced employee search using supported attributes."""
        payload = filters or {}
        conditions = []
        for key, column in ADVANCED_SEARCH_COLUMNS.items():
            value = _sanitize(payload.get(key))
            if not _non_empty(value):
                continue
            if key == "full_part_time":
                conditions.append(f"UPPER({column}) = UPPER('{value}')")
            else:
                conditions.append(f"UPPER({column}) LIKE UPPER('%{value}%')")

        if not conditions:
            return []

        return self._run_search(" AND ".join(conditions), limit)
