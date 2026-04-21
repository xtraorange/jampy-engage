"""SQLite demo/dev/test database helpers."""

from __future__ import annotations

import os
import random
import shutil
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


FIRST_NAMES = [
    "Avery", "Parker", "Morgan", "Blake", "Jordan", "Riley", "Cameron", "Taylor", "Drew", "Quinn",
    "Skyler", "Rowan", "Alex", "Casey", "Harper", "Reese", "Hayden", "Sawyer", "Emerson", "Finley",
]

LAST_NAMES = [
    "Carter", "Ellis", "Monroe", "Kendall", "Donovan", "Sutton", "Bennett", "Holland", "Merritt", "Palmer",
    "Sinclair", "Marlow", "Hadley", "Winslow", "Granger", "Calloway", "Sterling", "Alden", "Whitaker", "Delaney",
]

MIDDLE_NAMES = [
    "Lee", "Jude", "Kai", "Noel", "Ray", "Sage", "Lane", "Blair", "Skye", "Brooke",
]

JOB_PROFILES = [
    ("002148", "IT Portfolio Manager", "04ITEE", "ITPortMgr"),
    ("000760", "IT Business Analyst", "04IT44", "ITBA"),
    ("001110", "Supply Chain Planner", "04SC10", "SupplyChain"),
    ("001742", "Branch Operations Manager", "05OPS2", "BrOpsMgr"),
    ("000992", "Purchasing Analyst", "04PUR1", "Purchasing"),
    ("001401", "Data Reporting Analyst", "04ITBI", "DataReports"),
    ("001955", "Inventory Coordinator", "05INV1", "Inventory"),
    ("002020", "Contract Sales Specialist", "06SAL3", "ContractSales"),
    ("001608", "Regional HR Partner", "07HR22", "HumanResources"),
    ("001333", "Quality Process Lead", "08QL10", "Quality"),
]

LOCATIONS = ["HEADD", "MNMPLS", "PHXBRN", "ATLREG", "DALOPS", "SEATTL", "CHICTR", "DENHUB"]
BU_CODES = ["FCPUR", "FCOPS", "FCSLS", "FCIT", "FCHR"]
COMPANIES = ["PUR", "OPS", "SAL", "IT"]
TREE_BRANCHES = ["CORPORATE", "NORTH_AMERICA", "EUROPE", "ASIA"]
FTE_VALUES = ["F", "P"]

PREFERRED_VIEW_COLUMNS = [
    "EMPLOYEE_ID",
    "FIRST_NAME",
    "LAST_NAME",
    "USERNAME",
    "EMAIL",
    "SUPERVISOR_ID",
    "SUPERVISOR_NAME",
    "JOB_TITLE",
    "JOB_CODE",
    "DEPARTMENT_ID",
    "LOCATION",
    "BU_CODE",
    "COMPANY",
    "TREE_BRANCH",
]


def _schema_path(base_path: str) -> str:
    return os.path.join(base_path, "src", "data", "employee_mv_schema.sql")


def sqlite_db_path_from_config(base_path: str, config: Dict[str, Any]) -> str:
    configured = str(config.get("sqlite_db_path") or "").strip()
    if configured:
        if os.path.isabs(configured):
            return configured
        return os.path.join(base_path, configured)
    return os.path.join(base_path, "temp", "demo_dev_test.sqlite3")


def _random_date(rng: random.Random, start_year: int = 2010, end_year: int = 2026) -> str:
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    days = max((end - start).days, 1)
    value = start + timedelta(days=rng.randint(0, days))
    return f"{value.month}/{value.day}/{value.year}"


def _random_action_dt(rng: random.Random) -> str:
    base = datetime(2026, rng.randint(1, 12), rng.randint(1, 28), rng.randint(7, 18), rng.randint(0, 59), rng.randint(0, 59))
    hour = base.hour
    ampm = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    return f"{base.month}/{base.day}/{base.year} {hour12}:{base.minute:02d}:{base.second:02d} {ampm}"


def _build_username(first_name: str, last_name: str, idx: int) -> str:
    left = (first_name[:3] + last_name[:4]).lower()
    suffix = f"{idx % 1000:03d}"
    return (left + suffix)[:12]


def _full_name(last_name: str, first_name: str, middle_name: str) -> str:
    return f"{last_name},{first_name} {middle_name}".strip()


def generate_fake_employee_record(
    idx: int,
    rng: random.Random,
    supervisors: List[Dict[str, Any]],
) -> Dict[str, Any]:
    first_name = rng.choice(FIRST_NAMES)
    last_name = rng.choice(LAST_NAMES)
    middle_name = rng.choice(MIDDLE_NAMES)
    middle_init = middle_name[:1]

    job_code, job_title, department_id, dept_desc = rng.choice(JOB_PROFILES)
    location = rng.choice(LOCATIONS)
    bu_code = rng.choice(BU_CODES)
    company = rng.choice(COMPANIES)
    tree_branch = rng.choice(TREE_BRANCHES)

    employee_id = f"9{idx:06d}"
    username = _build_username(first_name, last_name, idx)
    preferred_name = f"{first_name} {last_name}"
    formal_cn = f"CN={preferred_name},OU=Accounts,OU=Resources,DC=example,DC=local"

    # Keep a realistic mix: many employees have supervisors, some are top-level.
    has_supervisor = bool(supervisors) and idx > 3 and rng.random() < 0.72
    supervisor = rng.choice(supervisors) if has_supervisor else None

    status = "A" if rng.random() > 0.05 else "T"
    hire_dt = _random_date(rng, 2012, 2025)
    termination_dt = _random_date(rng, 2025, 2026) if status == "T" else None

    record = {
        "EMPLOYEE_ID": employee_id,
        "EFF_DT": _random_date(rng, 2025, 2026),
        "EFF_SEQ": 0,
        "LOCATION": location,
        "DEPARTMENT_ID": department_id,
        "JOB_CODE": job_code,
        "JOB_TITLE": job_title,
        "NAME": _full_name(last_name, first_name, middle_name),
        "LAST_NAME": last_name,
        "FIRST_NAME": first_name,
        "MIDDLE_NAME": middle_name,
        "NAME_PSFORMAT": _full_name(last_name, first_name, middle_name),
        "SUPERVISOR_ID": supervisor.get("EMPLOYEE_ID") if supervisor else None,
        "SUPERVISOR_NAME": supervisor.get("NAME") if supervisor else None,
        "SUPERVISOR_JOB_CODE": supervisor.get("JOB_CODE") if supervisor else None,
        "SUPERVISOR_JOB_TITLE": supervisor.get("JOB_TITLE") if supervisor else None,
        "BU_CODE": bu_code,
        "COMPANY": company,
        "STATUS_CODE": status,
        "ACTION_DT": _random_action_dt(rng),
        "MIDDLE_INIT": middle_init,
        "TERMINATION_DT": termination_dt,
        "IS_KEY": 1 if rng.random() > 0.8 else 0,
        "DEPT_LOC_DESCSHRT": dept_desc,
        "HIRE_DT": hire_dt,
        "LAST_HIRE_DT": hire_dt,
        "FULL_PART_TIME": rng.choice(FTE_VALUES),
        "GL_EXPENSE": f"0{rng.randint(1, 9)}MN{rng.randint(100, 999)}",
        "USERNAME": username,
        "PREFERRED_NAME": preferred_name,
        "PHONE": f"(555){rng.randint(100, 999)}-{rng.randint(1000, 9999)}",
        "NAME_FORMAL_TXT": formal_cn,
        "MANAGER_ID": supervisor.get("USERNAME") if supervisor else None,
        "MOBILE_PHONE": f"(555){rng.randint(100, 999)}-{rng.randint(1000, 9999)}",
        "FAX": "",
        "FAS_RIGHTFAX": "",
        "EMAIL": f"{username}@example.test",
        "EMAIL2": f"{username}@mail.example.test",
        "APPROVER_ID": supervisor.get("EMPLOYEE_ID") if supervisor else None,
        "TREE_BRANCH": tree_branch,
    }

    return record


def _table_columns(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute("PRAGMA table_info(employee_mv)").fetchall()
    return [str(row[1]) for row in rows]


def create_or_reset_sqlite_db(base_path: str, db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with open(_schema_path(base_path), "r", encoding="utf-8") as schema_file:
        schema_sql = schema_file.read()
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema_sql)
        conn.commit()


def seed_sqlite_db(base_path: str, db_path: str, count: int = 250, seed: int = 42) -> int:
    if count < 1:
        return 0

    rng = random.Random(seed)
    create_or_reset_sqlite_db(base_path, db_path)

    with sqlite3.connect(db_path) as conn:
        columns = _table_columns(conn)
        placeholders = ", ".join(["?"] * len(columns))
        insert_sql = f"INSERT INTO employee_mv ({', '.join(columns)}) VALUES ({placeholders})"

        supervisors: List[Dict[str, Any]] = []
        rows = []
        for idx in range(1, count + 1):
            record = generate_fake_employee_record(idx, rng, supervisors)
            rows.append(tuple(record.get(column) for column in columns))

            if idx <= max(8, count // 8):
                supervisors.append(record)

        conn.executemany(insert_sql, rows)
        conn.commit()

    return count


def sqlite_status(base_path: str, db_path: str) -> Dict[str, Any]:
    exists = os.path.exists(db_path)
    status: Dict[str, Any] = {
        "db_path": db_path,
        "exists": exists,
        "table_exists": False,
        "row_count": 0,
    }
    if not exists:
        return status

    with sqlite3.connect(db_path) as conn:
        table_row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='employee_mv'"
        ).fetchone()
        if not table_row:
            return status

        status["table_exists"] = True
        status["columns"] = _table_columns(conn)
        count_row = conn.execute("SELECT COUNT(*) FROM employee_mv").fetchone()
        status["row_count"] = int(count_row[0] if count_row else 0)
    return status


def sqlite_columns(db_path: str) -> List[str]:
    if not os.path.exists(db_path):
        return []
    with sqlite3.connect(db_path) as conn:
        table_row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='employee_mv'"
        ).fetchone()
        if not table_row:
            return []
        return _table_columns(conn)


def sqlite_preview_rows(
    db_path: str,
    selected_columns: Optional[List[str]] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    cols = sqlite_columns(db_path)
    if not cols:
        return {
            "columns": [],
            "rows": [],
            "total_rows": 0,
            "limit": 0,
            "offset": 0,
        }

    allowed = set(cols)
    chosen = [c for c in (selected_columns or []) if c in allowed]
    if not chosen:
        preferred = [c for c in PREFERRED_VIEW_COLUMNS if c in allowed]
        chosen = preferred or cols[:12]

    safe_limit = max(1, min(int(limit or 50), 200))
    safe_offset = max(0, int(offset or 0))

    quoted = ", ".join([f'"{c}"' for c in chosen])
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        total_row = conn.execute("SELECT COUNT(*) AS CNT FROM employee_mv").fetchone()
        total_count = int(total_row["CNT"] if total_row else 0)
        data = conn.execute(
            f"SELECT {quoted} FROM employee_mv ORDER BY LAST_NAME, FIRST_NAME, EMPLOYEE_ID LIMIT ? OFFSET ?",
            (safe_limit, safe_offset),
        ).fetchall()

    return {
        "columns": chosen,
        "rows": [[row[c] for c in chosen] for row in data],
        "total_rows": total_count,
        "limit": safe_limit,
        "offset": safe_offset,
    }


def import_sqlite_snapshot(base_path: str, db_path: str, incoming_path: str) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    tmp_path = db_path + ".importing"
    shutil.copyfile(incoming_path, tmp_path)

    # Validate expected table exists before replacing active DB.
    with sqlite3.connect(tmp_path) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='employee_mv'"
        ).fetchone()
        if not row:
            raise ValueError("Snapshot file is missing employee_mv table.")

    os.replace(tmp_path, db_path)
