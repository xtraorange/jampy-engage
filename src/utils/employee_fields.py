"""Shared employee field metadata and row serialization helpers."""

from typing import Any

from .db_utils import row_value


EXPORTABLE_FIELDS = {
    "employee_id": "Employee ID",
    "username": "Username",
    "email": "Email",
    "job_title": "Job Title",
    "match_method": "Match Method",
    "department_id": "Department ID",
    "location": "Location",
    "bu_code": "Business Unit",
    "company": "Company",
    "tree_branch": "Tree Branch",
    "full_part_time": "Full/Part Time",
}

ADVANCED_SEARCH_COLUMNS = {
    "employee_id": "EMPLOYEE_ID",
    "first_name": "FIRST_NAME",
    "last_name": "LAST_NAME",
    "username": "USERNAME",
    "job_title": "JOB_TITLE",
    "department_id": "DEPARTMENT_ID",
    "location": "LOCATION",
    "bu_code": "BU_CODE",
    "company": "COMPANY",
    "tree_branch": "TREE_BRANCH",
    "full_part_time": "FULL_PART_TIME",
    "job_code": "JOB_CODE",
}

SEARCH_VALUE_COLUMNS = {
    "job_title": "JOB_TITLE",
    "employee_job_title": "JOB_TITLE",
    "location": "LOCATION",
    "bu_code": "BU_CODE",
    "company": "COMPANY",
    "tree_branch": "TREE_BRANCH",
    "department_id": "DEPARTMENT_ID",
    "first_name": "FIRST_NAME",
    "last_name": "LAST_NAME",
    "username": "USERNAME",
    "employee_id": "EMPLOYEE_ID",
    "job_code": "JOB_CODE",
}

EMPLOYEE_COLUMN_LABELS = {
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

EMPLOYEE_RESULT_FIELDS = [
    ("id", "EMPLOYEE_ID", 0),
    ("first_name", "FIRST_NAME", 1),
    ("last_name", "LAST_NAME", 2),
    ("username", "USERNAME", 3),
    ("email", "EMAIL", 4),
    ("job_title", "JOB_TITLE", 5),
    ("department_id", "DEPARTMENT_ID", 6),
    ("location", "LOCATION", 7),
    ("bu_code", "BU_CODE", 8),
    ("company", "COMPANY", 9),
    ("tree_branch", "TREE_BRANCH", 10),
    ("full_part_time", "FULL_PART_TIME", 11),
    ("job_code", "JOB_CODE", 12),
]


def label_for_column(column_name: str) -> str:
    """Return a user-facing label for a database column."""
    column = str(column_name or "").strip().upper()
    if column in EMPLOYEE_COLUMN_LABELS:
        return EMPLOYEE_COLUMN_LABELS[column]
    return column.replace("_", " ").title()


def serialize_employee_row(row: Any) -> dict[str, Any]:
    """Normalize a DB row from omsadm.employee_mv into the app payload shape."""
    return {
        field_name: row_value(row, column_name, fallback_index)
        for field_name, column_name, fallback_index in EMPLOYEE_RESULT_FIELDS
    }