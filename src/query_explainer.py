"""Plain-English query explanation helpers for query-builder payloads."""

from __future__ import annotations

from typing import Any, Dict, List


_HR = "-" * 84


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return [item for item in value if item not in (None, "")]
    if value in (None, ""):
        return []
    return [value]


def _str(value: Any) -> str:
    return str(value or "").strip()


def _block_comment(block: Dict[str, Any]) -> str:
    raw = block.get("comment") if isinstance(block, dict) else ""
    if not isinstance(raw, str):
        return ""
    flattened = " ".join(raw.replace("\r", "\n").splitlines())
    return " ".join(flattened.split()).strip()


def _person_label(person: Dict[str, Any]) -> str:
    first = _str(person.get("first_name"))
    last = _str(person.get("last_name"))
    username = _str(person.get("username") or person.get("person_username"))
    user_id = _str(person.get("user_id") or person.get("id") or person.get("person_id"))

    full_name = " ".join(part for part in [first, last] if part).strip()
    if full_name and username:
        return f"{full_name} ({username})"
    if full_name:
        return full_name
    if username:
        return username
    if user_id:
        return user_id
    return "(unknown person)"


def _normalize_people(values: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in _as_list(values):
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "first_name": _str(item.get("first_name")),
                "last_name": _str(item.get("last_name")),
                "username": _str(item.get("username") or item.get("person_username")),
                "user_id": _str(item.get("user_id") or item.get("id") or item.get("person_id")),
            }
        )
    return out


def _merge_people(primary: Any, details: Any) -> List[Dict[str, Any]]:
    base = _normalize_people(primary)
    extra = _normalize_people(details)
    if not base:
        return extra

    by_key = {}
    for person in extra:
        key = (_str(person.get("user_id")) or _str(person.get("username"))).lower()
        if key:
            by_key[key] = person

    merged = []
    for person in base:
        key = (_str(person.get("user_id")) or _str(person.get("username"))).lower()
        detail = by_key.get(key)
        if detail:
            merged.append(
                {
                    "first_name": _str(person.get("first_name") or detail.get("first_name")),
                    "last_name": _str(person.get("last_name") or detail.get("last_name")),
                    "username": _str(person.get("username") or detail.get("username")),
                    "user_id": _str(person.get("user_id") or detail.get("user_id")),
                }
            )
        else:
            merged.append(person)
    return merged


def _non_empty(lines: List[str]) -> List[str]:
    return [line for line in lines if _str(line)]


def _lines_for_values(title: str, values: Any) -> List[str]:
    vals = [_str(v) for v in _as_list(values) if _str(v)]
    if not vals:
        return []
    return [f"{title}:", *[f"- {value}" for value in vals]]


def _normalized_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(filters, dict):
        filters = {}
    return {
        "job_titles_display": _as_list(filters.get("job_titles_display") or filters.get("job_title_display") or filters.get("job_titles") or []),
        "job_codes": _as_list(filters.get("job_codes") or filters.get("job_code") or []),
        "bu_codes": _as_list(filters.get("bu_codes") or filters.get("bu_code") or []),
        "locations": _as_list(filters.get("locations") or filters.get("location") or []),
        "companies": _as_list(filters.get("companies") or filters.get("company") or []),
        "tree_branches": _as_list(filters.get("tree_branches") or filters.get("tree_branch") or []),
        "department_ids": _as_list(filters.get("department_ids") or filters.get("department_id") or []),
        "full_part_time": _str(filters.get("full_part_time")),
    }


def _filter_lines(filters: Dict[str, Any]) -> List[str]:
    f = _normalized_filters(filters)
    lines: List[str] = []
    lines.extend(_lines_for_values("Has a title/code of", f.get("job_titles_display") or f.get("job_codes")))
    lines.extend(_lines_for_values("Is in location", f.get("locations")))
    lines.extend(_lines_for_values("Is in business unit", f.get("bu_codes")))
    lines.extend(_lines_for_values("Is in company", f.get("companies")))
    lines.extend(_lines_for_values("Has a location/tree branch of", f.get("tree_branches")))
    lines.extend(_lines_for_values("Has department ID", f.get("department_ids")))
    if f.get("full_part_time"):
        lines.append(f"Employment type: {f.get('full_part_time')}")
    return lines


def _normalize_blocks(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    blocks = payload.get("blocks")
    if isinstance(blocks, list):
        return [block for block in blocks if isinstance(block, dict)]

    mode = _str(payload.get("mode"))
    if not mode:
        return []

    if mode == "by_person":
        return [
            {
                "type": "hierarchy_by_person",
                "persons": _merge_people(payload.get("persons"), payload.get("selected_person_details")),
                "direct_reports_only": bool(payload.get("direct_reports_only")),
                "include_root": bool(payload.get("include_root", not payload.get("exclude_root"))),
                "filters": {
                    "job_titles_display": payload.get("filter_job_titles_display") or payload.get("filter_job_titles") or [],
                    "job_codes": payload.get("filter_job_codes") or [],
                    "locations": payload.get("filter_locations") or [],
                    "bu_codes": payload.get("filter_bu_codes") or [],
                    "companies": payload.get("filter_companies") or [],
                    "tree_branches": payload.get("filter_tree_branches") or [],
                    "department_ids": payload.get("filter_department_ids") or [],
                    "full_part_time": payload.get("filter_full_part_time") or "",
                },
            }
        ]

    if mode in {"by_role", "by_attributes"}:
        return [
            {
                "type": "hierarchy_by_role",
                "attributes": {
                    "job_titles_display": payload.get("attributes_job_title_display") or [],
                    "job_codes": payload.get("attributes_job_code") or [],
                    "locations": payload.get("attributes_location") or [],
                    "bu_codes": payload.get("attributes_bu_code") or [],
                    "companies": payload.get("attributes_company") or [],
                    "tree_branches": payload.get("attributes_tree_branch") or [],
                    "department_ids": payload.get("attributes_department_id") or [],
                },
                "direct_reports_only": bool(payload.get("direct_reports_only")),
                "include_root": bool(payload.get("include_root", True)),
                "filters": {
                    "job_titles_display": payload.get("filter_job_titles_display") or payload.get("filter_job_titles") or [],
                    "job_codes": payload.get("filter_job_codes") or [],
                    "locations": payload.get("filter_locations") or [],
                    "bu_codes": payload.get("filter_bu_codes") or [],
                    "companies": payload.get("filter_companies") or [],
                    "tree_branches": payload.get("filter_tree_branches") or [],
                    "department_ids": payload.get("filter_department_ids") or [],
                    "full_part_time": payload.get("filter_full_part_time") or "",
                },
            }
        ]

    return [
        {
            "type": "filtered_population",
            "filters": {
                "job_titles_display": payload.get("filter_job_titles_display") or payload.get("filter_job_titles") or [],
                "job_codes": payload.get("filter_job_codes") or [],
                "locations": payload.get("filter_locations") or [],
                "bu_codes": payload.get("filter_bu_codes") or [],
                "companies": payload.get("filter_companies") or [],
                "tree_branches": payload.get("filter_tree_branches") or [],
                "department_ids": payload.get("filter_department_ids") or [],
                "full_part_time": payload.get("filter_full_part_time") or "",
            },
        }
    ]


def _describe_block(block: Dict[str, Any]) -> str:
    block_type = _str(block.get("type") or "filtered_population")
    lines: List[str] = []

    if block_type == "hierarchy_by_person":
        roots = _merge_people(block.get("persons"), block.get("selected_person_details"))
        root_lines = [f"- {_person_label(person)}" for person in roots] or ["- (none selected)"]
        lines.append("Find anyone in the reporting hierarchy of these people:")
        lines.extend(root_lines)

        include_root = bool(block.get("include_root", not block.get("exclude_root")))
        lines.append("Root person is included in results." if include_root else "Root person is excluded from results.")
        if bool(block.get("direct_reports_only")):
            lines.append("Only direct reports are included.")

        filters = _filter_lines(block.get("filters") or {})
        if filters:
            lines.append("Then keep only people who meet these conditions:")
            lines.extend(filters)
        return "\n".join(_non_empty(lines))

    if block_type == "hierarchy_by_role":
        attrs = block.get("attributes") or {}
        role_lines: List[str] = []
        role_lines.extend(_lines_for_values("Title/code", attrs.get("job_titles_display") or attrs.get("job_codes")))
        role_lines.extend(_lines_for_values("Location", attrs.get("locations")))
        role_lines.extend(_lines_for_values("Business unit", attrs.get("bu_codes")))
        role_lines.extend(_lines_for_values("Company", attrs.get("companies")))
        role_lines.extend(_lines_for_values("Location/tree branch", attrs.get("tree_branches")))
        role_lines.extend(_lines_for_values("Department ID", attrs.get("department_ids")))

        lines.append("Find the appropriate leader(s) for the hierarchy by matching these conditions:")
        lines.extend(role_lines or ["- (no root attributes selected)"])

        include_root = bool(block.get("include_root", True))
        if bool(block.get("direct_reports_only")):
            lines.append("Only direct reports are included.")

        filters = _filter_lines(block.get("filters") or {})
        if filters:
            lines.append("")
            lines.append("Then keep only people who meet these conditions:")
            lines.extend(filters)
        lines.append("")
        lines.append("Also include the hierarchy leader(s)." if include_root else "Do not include the hierarchy leader(s).")
        return "\n".join(lines)

    if block_type == "manual_individuals":
        people = _merge_people(block.get("persons"), block.get("selected_person_details"))
        lines.append("Include these specific people directly:")
        lines.extend([f"- {_person_label(person)}" for person in people] or ["- (none selected)"])
        return "\n".join(_non_empty(lines))

    lines.append("Start from all active employees.")
    filters = _filter_lines(block.get("filters") or {})
    if filters:
        lines.append("")
        lines.append("Keep only people who meet these conditions:")
        lines.extend(filters)
    else:
        lines.append("No additional filters are applied.")
    return "\n".join(lines)


def explain_builder_query(payload: Dict[str, Any]) -> str:
    """Return a plain-English explanation of query-builder parameters."""
    if not isinstance(payload, dict):
        return "No query-builder configuration was provided."

    blocks = _normalize_blocks(payload)
    if not blocks:
        return "No query-builder source blocks are configured yet."

    has_multiple_sources = len(blocks) > 1
    if not has_multiple_sources:
        comment = _block_comment(blocks[0])
        described = _describe_block(blocks[0]).strip()
        if comment:
            return f"- {comment}\n{described}".strip()
        return described

    parts: List[str] = ["This query returns the combination of these sources:", ""]
    total_blocks = len(blocks)
    for index, block in enumerate(blocks, start=1):
        section = [_HR, f"Source {index}"]
        comment = _block_comment(block)
        if comment:
            section.append(f"- {comment}")
        section.extend([
            _HR,
            _describe_block(block),
            _HR,
        ])
        parts.extend(section)
        if index < total_blocks:
            parts.extend(["", ""])

    return "\n".join(parts).strip()
