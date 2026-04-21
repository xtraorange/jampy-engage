import csv
import os
import re
import sqlite3
import threading
import time
from datetime import datetime
from typing import Any, Dict, List

import jampy_db
import yaml

try:
    from flask import g, has_request_context
except Exception:  # pragma: no cover - flask is always available for UI usage
    g = None

    def has_request_context():
        return False


def _query_label(query: str) -> str:
    compact = " ".join(str(query or "").strip().split())
    if not compact:
        return "(empty query)"
    return compact[:160] + ("..." if len(compact) > 160 else "")


def _record_request_query_timing(query: str, elapsed_ms: float, row_count: int) -> None:
    if not has_request_context() or g is None:
        return

    if not hasattr(g, "db_query_timings"):
        g.db_query_timings = []
    if not hasattr(g, "db_query_total_ms"):
        g.db_query_total_ms = 0.0

    g.db_query_timings.append(
        {
            "label": _query_label(query),
            "elapsed_ms": round(float(elapsed_ms), 2),
            "row_count": int(row_count),
        }
    )
    g.db_query_total_ms = float(getattr(g, "db_query_total_ms", 0.0)) + float(elapsed_ms)


_FETCH_FIRST_RE = re.compile(r"FETCH\s+FIRST\s+(\d+)\s+ROWS\s+ONLY", re.IGNORECASE)
_OFFSET_FETCH_RE = re.compile(
    r"OFFSET\s+(\d+)\s+ROWS\s+FETCH\s+NEXT\s+(\d+)\s+ROWS\s+ONLY",
    re.IGNORECASE,
)
_CONNECT_BLOCK_RE = re.compile(
    r"""
SELECT\s+EMPLOYEE_ID\s*,\s*USERNAME\s*,\s*JOB_CODE\s*,\s*DEPARTMENT_ID\s*,\s*BU_CODE\s*,\s*
LOCATION\s*,\s*COMPANY\s*,\s*TREE_BRANCH\s*,\s*FULL_PART_TIME\s*,\s*LEVEL\s+AS\s+HIER_LEVEL\s*
FROM\s+employee_mv\s*
START\s+WITH\s*(?P<start>.*?)\s*
CONNECT\s+BY\s+PRIOR\s+EMPLOYEE_ID\s*=\s*SUPERVISOR_ID\s*
AND\s*(?P<cond>.*?)(?=(?:\n\s*UNION\s+ALL|\)\s*cte|\)\s*merged|$))
""",
    re.IGNORECASE | re.DOTALL | re.VERBOSE,
)

_QUALIFIABLE_COLUMNS = [
    "STATUS_CODE",
    "USERNAME",
    "EMPLOYEE_ID",
    "JOB_CODE",
    "DEPARTMENT_ID",
    "BU_CODE",
    "LOCATION",
    "COMPANY",
    "TREE_BRANCH",
    "FULL_PART_TIME",
    "SUPERVISOR_ID",
]


def _runtime_db_config() -> Dict[str, Any]:
    cfg_path = os.path.join(os.getcwd(), "config", "general.yaml")
    if not os.path.exists(cfg_path):
        return {}
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
            return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def _sqlite_db_path_from_config(config: Dict[str, Any]) -> str:
    raw = str(config.get("sqlite_db_path") or "").strip()
    if raw:
        return raw if os.path.isabs(raw) else os.path.join(os.getcwd(), raw)
    return os.path.join(os.getcwd(), "temp", "demo_dev_test.sqlite3")


def _qualify_recursive_condition(cond: str) -> str:
    rewritten = str(cond or "")
    for column in _QUALIFIABLE_COLUMNS:
        rewritten = re.sub(
            rf"(?<![\.\w]){column}(?![\w])",
            f"e.{column}",
            rewritten,
            flags=re.IGNORECASE,
        )
    return rewritten


def _translate_connect_by_blocks(query: str) -> str:
    ctes: List[str] = []
    counter = 0

    def _replace(match: re.Match) -> str:
        nonlocal counter
        counter += 1
        cte_name = f"h{counter}"
        start_clause = str(match.group("start") or "").strip()
        cond_clause = _qualify_recursive_condition(str(match.group("cond") or "").strip())

        ctes.append(
            f"""{cte_name}(EMPLOYEE_ID, USERNAME, JOB_CODE, DEPARTMENT_ID, BU_CODE, LOCATION, COMPANY, TREE_BRANCH, FULL_PART_TIME, HIER_LEVEL) AS (
    SELECT EMPLOYEE_ID, USERNAME, JOB_CODE, DEPARTMENT_ID, BU_CODE, LOCATION, COMPANY, TREE_BRANCH, FULL_PART_TIME, 1 AS HIER_LEVEL
    FROM employee_mv
    WHERE {start_clause}
    UNION ALL
    SELECT e.EMPLOYEE_ID, e.USERNAME, e.JOB_CODE, e.DEPARTMENT_ID, e.BU_CODE, e.LOCATION, e.COMPANY, e.TREE_BRANCH, e.FULL_PART_TIME, p.HIER_LEVEL + 1 AS HIER_LEVEL
    FROM employee_mv e
    JOIN {cte_name} p ON e.SUPERVISOR_ID = p.EMPLOYEE_ID
    WHERE {cond_clause}
)"""
        )

        return (
            "SELECT EMPLOYEE_ID, USERNAME, JOB_CODE, DEPARTMENT_ID, BU_CODE, LOCATION, "
            f"COMPANY, TREE_BRANCH, FULL_PART_TIME, HIER_LEVEL FROM {cte_name}"
        )

    rewritten = _CONNECT_BLOCK_RE.sub(_replace, query)
    if not ctes:
        return rewritten

    return "WITH RECURSIVE\n" + ",\n".join(ctes) + "\n" + rewritten


def _translate_oracle_sql_for_sqlite(query: str) -> str:
    translated = str(query or "")
    translated = re.sub(r"\bomsadm\.employee_mv\b", "employee_mv", translated, flags=re.IGNORECASE)
    translated = _translate_connect_by_blocks(translated)
    translated = re.sub(r"\bNVL\s*\(", "COALESCE(", translated, flags=re.IGNORECASE)
    translated = _OFFSET_FETCH_RE.sub(lambda m: f"LIMIT {m.group(2)} OFFSET {m.group(1)}", translated)
    translated = _FETCH_FIRST_RE.sub(lambda m: f"LIMIT {m.group(1)}", translated)
    return translated


def _all_tab_columns_as_rows(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute("PRAGMA table_info(employee_mv)").fetchall()
    return [{"COLUMN_NAME": str(row[1]).upper()} for row in rows]


def _ensure_sqlite_schema(conn: sqlite3.Connection) -> None:
    table_row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='employee_mv'"
    ).fetchone()
    if table_row:
        return

    schema_path = os.path.join(os.getcwd(), "src", "data", "employee_mv_schema.sql")
    if not os.path.exists(schema_path):
        return
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
            conn.commit()
    except Exception:
        pass


class DatabaseExecutor:
    def __init__(self, tns: str, profile: str = "oracle_thick_external", **props):
        cfg = _runtime_db_config()
        self.environment = str(cfg.get("db_environment") or "oracle").strip().lower()
        self.client = None
        self._sqlite_conn = None
        self._lock = threading.Lock()

        if self.environment == "sqlite":
            db_path = _sqlite_db_path_from_config(cfg)
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self._sqlite_conn = sqlite3.connect(db_path, check_same_thread=False)
            self._sqlite_conn.row_factory = sqlite3.Row
            _ensure_sqlite_schema(self._sqlite_conn)
        else:
            # build a shared jampy_db client; extra props may include client_folder,
            # lib_dir, config_dir, or any other profile-specific keyword arguments.
            self.client = jampy_db.create(profile, tnsname=tns, **props)

    def _run_sqlite_query(self, query: str) -> List[Any]:
        if self._sqlite_conn is None:
            return []

        if re.search(r"\bALL_TAB_COLUMNS\b", str(query or ""), flags=re.IGNORECASE):
            return _all_tab_columns_as_rows(self._sqlite_conn)

        sql = _translate_oracle_sql_for_sqlite(query)
        with self._lock:
            cursor = self._sqlite_conn.cursor()
            cursor.execute(sql)
            if cursor.description is None:
                self._sqlite_conn.commit()
                return []
            data = cursor.fetchall()
            columns = [str(col[0]).upper() for col in (cursor.description or [])]
            return [{columns[i]: row[i] for i in range(len(columns))} for row in data]

    def run_query(self, query: str) -> List[Any]:
        started = time.perf_counter()
        if self.environment == "sqlite":
            rows = self._run_sqlite_query(query)
        else:
            # execute synchronously; default return_type 'rows' returns list of dicts
            job = self.client.query(query, return_type="rows", run_async=False)
            rows = job.result()
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        row_count = len(rows) if isinstance(rows, list) else 0
        _record_request_query_timing(query, elapsed_ms, row_count)
        return rows

    def write_csv(self, rows: Any, headers: Any, out_file: str) -> None:
        """Write provided rows to CSV with required ObjectId header.

        Each row should be an iterable of values; the caller is responsible for
        collapsing to a single email column if desired.
        """
        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        with open(out_file, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["ObjectId"])
            for row in rows:
                writer.writerow(row)

    def close(self) -> None:
        if self.client is not None:
            try:
                self.client.close()
            except Exception:
                pass
        if self._sqlite_conn is not None:
            try:
                self._sqlite_conn.close()
            except Exception:
                pass


# simple progress tracker shared among threads
class ProgressTracker:
    def __init__(self, total: int):
        self.lock = threading.Lock()
        self.total = total
        self.done = 0
        self.status: Dict[str, str] = {}
        self.results: Dict[str, dict] = {}  # Store group results including csv_path

    def update(self, handle: str, msg: str):
        with self.lock:
            self.status[handle] = msg
            self._print_status()

    def set_result(self, handle: str, result: dict):
        """Store result information for a group."""
        with self.lock:
            self.results[handle] = result

    def increment(self, handle: str):
        with self.lock:
            self.done += 1
            self._print_status()

    def _print_status(self):
        lines = [f"{h}: {s}" for h, s in self.status.items()]
        pct = (self.done / self.total * 100) if self.total else 0
        lines.append(f"Completed {self.done}/{self.total} ({pct:.0f}% )")
        # print progress without clearing screen so terminal output remains readable
        print("\n".join(lines))
