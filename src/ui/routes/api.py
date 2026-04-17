"""API routes for AJAX calls."""
from flask import Blueprint, request, jsonify
import os
import sys
from datetime import datetime

from ...services.config_service import ConfigService
from ...services.adhoc_service import (
    build_custom_employee_sql,
    label_for_column,
    load_employee_mv_columns,
)
from ...services.employee_lookup_service import EmployeeLookupService
from ...sql_builder import generate_safe_hierarchy_sql
from ...query_explainer import explain_builder_query
from ...db import DatabaseExecutor
from ...utils import ACTIVE_EMPLOYEE_FILTER, SEARCH_VALUE_COLUMNS, extract_count_value, row_value, single_or_in_condition


def init_api_routes(app, base_path: str):
    """Initialize API routes with dependencies."""
    api_bp = Blueprint('api', __name__)
    config_service = ConfigService(base_path)

    @api_bp.route("/api/search-employees", methods=["GET"])
    def search_employees():
        """Typeahead search for employees."""
        cfg = config_service.load_general_config()
        query = request.args.get("q", "").strip()
        scope = request.args.get("scope", "basic").strip().lower()

        if not query or len(query) < 2:
            return jsonify([])

        try:
            lookup_service = EmployeeLookupService(cfg.get("oracle_tns"))
            if scope == "advanced":
                items = lookup_service.search_candidates(query=query, limit=20)
            else:
                items = lookup_service.search_candidates_basic(query=query, limit=20)
            return jsonify(items)
        except Exception as e:
            import traceback, logging, os
            err_msg = str(e)
            # Write detailed error to log file in base path
            log_path = os.path.join(os.getcwd(), 'error.log')
            with open(log_path, 'a', encoding='utf-8') as logf:
                logf.write(f"[{datetime.now()}] Search error for '{query}': {err_msg}\n")
                logf.write(traceback.format_exc())
                logf.write("\n---\n")
            print(f"DEBUG: Search error logged to {log_path}")
            # return full message if short number or generic
            return jsonify({"error": err_msg}), 500

    @api_bp.route("/api/search-employees-advanced", methods=["POST"])
    def search_employees_advanced():
        """Advanced employee search by supported attributes."""
        cfg = config_service.load_general_config()
        payload = request.get_json(silent=True) or {}
        filters = payload.get("filters") if isinstance(payload.get("filters"), dict) else payload
        if not isinstance(filters, dict):
            filters = {}

        if not any(str(value or "").strip() for value in filters.values()):
            return jsonify([])

        try:
            lookup_service = EmployeeLookupService(cfg.get("oracle_tns"))
            items = lookup_service.search_candidates_advanced(filters=filters, limit=100)
            return jsonify(items)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @api_bp.route("/api/adhoc-report-columns", methods=["GET"])
    def adhoc_report_columns():
        """Return the available employee_mv columns for ad hoc custom reporting."""
        cfg = config_service.load_general_config()
        columns = load_employee_mv_columns(cfg.get("oracle_tns"))
        return jsonify([
            {
                "column": column,
                "label": label_for_column(column),
            }
            for column in columns
        ])

    @api_bp.route("/api/adhoc-custom-report-sql", methods=["POST"])
    def adhoc_custom_report_sql():
        """Build validated SQL for the ad hoc custom report workflow."""
        cfg = config_service.load_general_config()
        payload = request.get_json(silent=True) or {}
        selected_columns = payload.get("selected_columns") or []
        filters = payload.get("filters") or []
        allowed_columns = load_employee_mv_columns(cfg.get("oracle_tns"))
        try:
            sql = build_custom_employee_sql(selected_columns, filters, allowed_columns)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"sql": sql})

    @api_bp.route("/api/adhoc-custom-report-count", methods=["POST"])
    def adhoc_custom_report_count():
        """Count rows for the ad hoc custom report workflow."""
        cfg = config_service.load_general_config()
        payload = request.get_json(silent=True) or {}
        selected_columns = payload.get("selected_columns") or []
        filters = payload.get("filters") or []
        allowed_columns = load_employee_mv_columns(cfg.get("oracle_tns"))
        try:
            sql = build_custom_employee_sql(selected_columns, filters, allowed_columns)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        executor = DatabaseExecutor(cfg.get("oracle_tns"))
        try:
            count = extract_count_value(executor.run_query(f"SELECT COUNT(*) AS CNT FROM ({sql})"))
        finally:
            executor.close()
        return jsonify({"count": count, "sql": sql})


    @api_bp.route("/api/get-all-values", methods=["GET"])
    def get_all_values():
        """Generic endpoint to get all unique values for a field."""
        cfg = config_service.load_general_config()
        field = request.args.get("field", "").strip()
        
        # Map field names to column names
        if field not in SEARCH_VALUE_COLUMNS:
            return jsonify({"error": "Invalid field"}), 400
            
        column = SEARCH_VALUE_COLUMNS[field]
        
        try:
            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            sql = f"SELECT DISTINCT {column} FROM omsadm.employee_mv WHERE {column} IS NOT NULL AND {ACTIVE_EMPLOYEE_FILTER} ORDER BY {column}"
            results = executor.run_query(sql)
            items = [row[0] if isinstance(row, (list, tuple)) else next(iter(row.values())) for row in results]
            executor.close()
            return jsonify(items)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @api_bp.route("/api/search-values", methods=["GET"])
    def search_values():
        """Generic endpoint for live search of field values."""
        cfg = config_service.load_general_config()
        field = request.args.get("field", "").strip()
        query = request.args.get("q", "").strip()
        
        if not query or len(query) < 1:
            return jsonify([])
            
        # Map field names to column names
        if field not in SEARCH_VALUE_COLUMNS:
            return jsonify({"error": "Invalid field"}), 400
            
        try:
            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            if field == "job_title":
                # Special case: search both JOB_CODE and JOB_TITLE
                sql = f"SELECT DISTINCT JOB_CODE || ' - ' || JOB_TITLE as value FROM omsadm.employee_mv WHERE (UPPER(JOB_CODE) LIKE UPPER('%{query}%') OR UPPER(JOB_TITLE) LIKE UPPER('%{query}%')) AND {ACTIVE_EMPLOYEE_FILTER} ORDER BY value"
            elif field == "employee_job_title":
                sql = f"SELECT DISTINCT JOB_TITLE as value FROM omsadm.employee_mv WHERE UPPER(JOB_TITLE) LIKE UPPER('%{query}%') AND JOB_TITLE IS NOT NULL AND {ACTIVE_EMPLOYEE_FILTER} ORDER BY value"
            else:
                column = SEARCH_VALUE_COLUMNS[field]
                sql = f"SELECT DISTINCT {column} FROM omsadm.employee_mv WHERE UPPER({column}) LIKE UPPER('%{query}%') AND {ACTIVE_EMPLOYEE_FILTER} ORDER BY {column}"
            
            results = executor.run_query(sql)
            items = []
            for row in results[:20]:
                if isinstance(row, dict):
                    value = next(iter(row.values()), None)
                else:
                    value = row[0]
                items.append({"value": value})
            executor.close()
            return jsonify(items)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @api_bp.route("/api/preview-role-roots", methods=["GET"])
    def preview_role_roots():
        """Preview employees selected as hierarchy roots in By Role mode."""
        cfg = config_service.load_general_config()
        job_titles = [value.strip().replace("'", "''") for value in request.args.getlist("job_title") if value.strip()]
        locations = [value.strip().replace("'", "''") for value in request.args.getlist("location") if value.strip()]
        bu_codes = [value.strip().replace("'", "''") for value in request.args.getlist("bu_code") if value.strip()]
        companies = [value.strip().replace("'", "''") for value in request.args.getlist("company") if value.strip()]
        tree_branches = [value.strip().replace("'", "''") for value in request.args.getlist("tree_branch") if value.strip()]
        department_ids = [value.strip().replace("'", "''") for value in request.args.getlist("department_id") if value.strip()]

        # Require at least one attribute to avoid huge unfiltered queries.
        if not (job_titles or locations or bu_codes or companies or tree_branches or department_ids):
            return jsonify([])

        where_parts = [ACTIVE_EMPLOYEE_FILTER]
        if job_titles:
            job_codes = [value.split(" - ", 1)[0].strip() for value in job_titles]
            where_parts.append(single_or_in_condition("JOB_CODE", job_codes))
        if locations:
            where_parts.append(single_or_in_condition("LOCATION", locations))
        if bu_codes:
            where_parts.append(single_or_in_condition("BU_CODE", bu_codes))
        if companies:
            where_parts.append(single_or_in_condition("COMPANY", companies))
        if tree_branches:
            where_parts.append(single_or_in_condition("TREE_BRANCH", tree_branches))
        if department_ids:
            where_parts.append(single_or_in_condition("DEPARTMENT_ID", department_ids))

        sql = f"""
        SELECT EMPLOYEE_ID, FIRST_NAME, LAST_NAME, USERNAME, JOB_TITLE
        FROM omsadm.employee_mv
        WHERE {' AND '.join(where_parts)}
        ORDER BY FIRST_NAME, LAST_NAME
        FETCH FIRST 25 ROWS ONLY
        """

        try:
            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            results = executor.run_query(sql)
            items = []
            for row in results:
                if isinstance(row, dict):
                    items.append({
                        "id": row.get("EMPLOYEE_ID") or row.get("employee_id"),
                        "first_name": row.get("FIRST_NAME") or row.get("first_name"),
                        "last_name": row.get("LAST_NAME") or row.get("last_name"),
                        "username": row.get("USERNAME") or row.get("username"),
                        "job_title": row.get("JOB_TITLE") or row.get("job_title"),
                    })
                else:
                    items.append({
                        "id": row[0],
                        "first_name": row[1],
                        "last_name": row[2],
                        "username": row[3],
                        "job_title": row[4],
                    })
            executor.close()
            return jsonify(items)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @api_bp.route("/api/role-attribute-share-counts", methods=["POST"])
    def role_attribute_share_counts():
        """Return active-employee share counts for selected By Role attribute values."""
        cfg = config_service.load_general_config()
        payload = request.get_json(silent=True) or {}
        attributes = payload.get("attributes") or {}

        attr_map = {
            "job_title": "JOB_CODE",
            "department_id": "DEPARTMENT_ID",
            "location": "LOCATION",
            "bu_code": "BU_CODE",
            "company": "COMPANY",
            "tree_branch": "TREE_BRANCH",
        }

        results = {}
        try:
            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            for key, column in attr_map.items():
                raw_values = attributes.get(key) or []
                values = [str(value).strip() for value in raw_values if str(value).strip()]
                if key == "job_title":
                    values = [value.split(" - ", 1)[0].strip() for value in values]

                values = [value.replace("'", "''") for value in values if value]
                if not values:
                    results[key] = 0
                    continue

                condition = single_or_in_condition(column, values)
                sql = f"""
                SELECT COUNT(*) AS CNT
                FROM omsadm.employee_mv
                WHERE {ACTIVE_EMPLOYEE_FILTER}
                  AND {condition}
                """
                row = executor.run_query(sql)
                if row and isinstance(row[0], dict):
                    results[key] = int(row[0].get("CNT") or row[0].get("cnt") or 0)
                elif row:
                    results[key] = int(row[0][0])
                else:
                    results[key] = 0
            executor.close()
            return jsonify(results)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @api_bp.route("/api/search-tree-branches", methods=["GET"])
    def search_tree_branches():
        """Typeahead search for tree branches."""
        cfg = config_service.load_general_config()
        query = request.args.get("q", "").strip()

        if not query or len(query) < 1:
            return jsonify([])

        try:
            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            sql = f"SELECT DISTINCT TREE_BRANCH FROM omsadm.employee_mv WHERE UPPER(TREE_BRANCH) LIKE UPPER('%{query}%') AND {ACTIVE_EMPLOYEE_FILTER} ORDER BY TREE_BRANCH"
            results = executor.run_query(sql)
            items = []
            for row in results[:20]:
                if isinstance(row, dict):
                    value = next(iter(row.values()), None)
                else:
                    value = row[0]
                items.append({"value": value})
            executor.close()
            return jsonify(items)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @api_bp.route("/api/generate-builder-sql", methods=["POST"])
    def generate_builder_sql():
        """Generate SQL from builder parameters."""
        try:
            data = request.get_json()

            sql = generate_safe_hierarchy_sql(**data)
            return jsonify({"sql": sql})
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @api_bp.route("/api/explain-builder-query", methods=["POST"])
    def explain_builder_query_api():
        """Generate plain-English explanation from builder parameters."""
        try:
            data = request.get_json(silent=True) or {}
            text = explain_builder_query(data)
            return jsonify({"text": text})
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @api_bp.route("/api/test-query", methods=["POST"])
    def test_query():
        """Test a query and return record count."""
        try:
            cfg = config_service.load_general_config()
            data = request.get_json()
            sql = data.get("sql", "").strip()

            if not sql:
                return jsonify({"error": "No SQL provided"}), 400

            executor = DatabaseExecutor(cfg.get("oracle_tns"))
            # Count records
            count_sql = f"SELECT COUNT(*) FROM ({sql})"
            result = executor.run_query(count_sql)
            count = extract_count_value(result)
            executor.close()

            return jsonify({"count": count})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @api_bp.route("/api/test-query-details", methods=["POST"])
    def test_query_details():
        """Return count and paginated rows (email/name/title) for a query."""
        try:
            cfg = config_service.load_general_config()
            data = request.get_json(silent=True) or {}
            sql = str(data.get("sql", "")).strip()
            if not sql:
                return jsonify({"error": "No SQL provided"}), 400

            try:
                page = max(int(data.get("page", 1)), 1)
            except (TypeError, ValueError):
                page = 1

            try:
                page_size = int(data.get("page_size", 100))
            except (TypeError, ValueError):
                page_size = 100
            page_size = min(max(page_size, 1), 200)

            offset = (page - 1) * page_size

            executor = DatabaseExecutor(cfg.get("oracle_tns"))

            base_users_sql = f"SELECT DISTINCT USERNAME FROM ({sql})"
            count_sql = f"SELECT COUNT(*) AS CNT FROM ({base_users_sql})"
            total_count = extract_count_value(executor.run_query(count_sql))

            paged_sql = f"""
            SELECT base.USERNAME AS EMAIL,
                   NVL(emp.FIRST_NAME, '') AS FIRST_NAME,
                   NVL(emp.LAST_NAME, '') AS LAST_NAME,
                   NVL(emp.JOB_TITLE, '') AS JOB_TITLE
            FROM ({base_users_sql}) base
            LEFT JOIN omsadm.employee_mv emp
              ON UPPER(emp.USERNAME) = UPPER(base.USERNAME)
            ORDER BY NVL(emp.LAST_NAME, 'ZZZZZZ'), NVL(emp.FIRST_NAME, 'ZZZZZZ'), base.USERNAME
            OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY
            """
            records = executor.run_query(paged_sql)
            executor.close()

            rows = []
            for row in records:
                email = str(row_value(row, "EMAIL", 0) or "")
                first = str(row_value(row, "FIRST_NAME", 1) or "").strip()
                last = str(row_value(row, "LAST_NAME", 2) or "").strip()
                title = str(row_value(row, "JOB_TITLE", 3) or "").strip()
                full_name = " ".join(part for part in (first, last) if part).strip()
                rows.append({
                    "email": email,
                    "name": full_name,
                    "title": title,
                })

            total_pages = max((total_count + page_size - 1) // page_size, 1)
            return jsonify({
                "count": total_count,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "rows": rows,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @api_bp.route("/api/pick-folder")
    def pick_folder():
        """Open a native folder picker dialog."""
        try:
            # Try Windows Shell API first (fastest, no window)
            import ctypes
            import ctypes.wintypes as wintypes
            from ctypes import c_char_p, pointer, POINTER, Structure

            class BROWSEINFO(Structure):
                _fields_ = [
                    ("hwndOwner", wintypes.HWND),
                    ("pidlRoot", wintypes.c_void_p),
                    ("pszDisplayName", ctypes.c_char_p),
                    ("lpszTitle", wintypes.LPCSTR),
                    ("ulFlags", wintypes.UINT),
                    ("lpfn", wintypes.c_void_p),
                    ("lParam", wintypes.LPARAM),
                    ("iImage", wintypes.c_int),
                ]

            shell32 = ctypes.windll.shell32
            ole32 = ctypes.windll.ole32

            # Initialize COM
            ole32.CoInitialize(None)

            # Set up browse info
            bi = BROWSEINFO()
            bi.hwndOwner = None
            bi.pidlRoot = None
            bi.pszDisplayName = ctypes.create_string_buffer(4096)
            bi.lpszTitle = b"Select a folder"
            bi.ulFlags = 0x0001  # BIF_RETURNONLYFSDIRS

            # Show picker
            pidl = shell32.SHBrowseForFolder(pointer(bi))
            if pidl:
                path_buffer = ctypes.create_unicode_buffer(4096)
                shell32.SHGetPathFromIDListW(pidl, path_buffer)
                folder = path_buffer.value
                # Free PIDL
                ole32.CoTaskMemFree(pidl)
                ole32.CoUninitialize()
                if folder:
                    return jsonify(path=folder)
            ole32.CoUninitialize()
            return jsonify(cancelled=True)

        except Exception:
            # Fall back to tkinter
            try:
                import tkinter as tk
                from tkinter.filedialog import askdirectory

                root = tk.Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                folder = askdirectory(title="Select a folder")
                root.destroy()

                if folder:
                    return jsonify(path=folder)
                else:
                    return jsonify(cancelled=True)
            except ImportError:
                return jsonify(error="tkinter not installed"), 200
            except Exception as e:
                return jsonify(error=str(e)), 200

    @api_bp.route("/api/view-report", methods=["GET"])
    def view_report():
        """Retrieve report content as JSON for display in modal."""
        from flask import current_app
        handle = request.args.get("handle", "").strip()
        
        if not handle:
            return jsonify({"error": "No handle provided"}), 400
        
        tracker = current_app.config.get("tracker")
        if not tracker:
            return jsonify({"error": "No job running"}), 400
        
        result = tracker.results.get(handle)
        if not result:
            return jsonify({"error": "Group not found or not completed yet"}), 404
        
        csv_path = result.get("csv_path")
        if not csv_path:
            return jsonify({"error": "Report file not available"}), 404
        
        try:
            # Read CSV file
            import csv
            parsed_rows = []
            headers = []
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                first_row = next(reader, None)

                if first_row and any(str(cell).strip() for cell in first_row):
                    headers = [str(cell).strip() or f"column_{index + 1}" for index, cell in enumerate(first_row)]

                for row in reader:
                    if not row or not any(str(cell).strip() for cell in row):
                        continue
                    parsed_rows.append(row)

            if parsed_rows:
                max_cols = max(len(row) for row in parsed_rows)
            else:
                max_cols = len(headers) if headers else 1

            # Fall back to synthetic headers if file had no header row.
            if not headers:
                if max_cols == 1:
                    headers = ["email"]
                else:
                    headers = [f"column_{index + 1}" for index in range(max_cols)]
            elif len(headers) < max_cols:
                headers.extend([f"column_{index + 1}" for index in range(len(headers), max_cols)])
            elif len(headers) > max_cols:
                max_cols = len(headers)

            rows = [row + [""] * (max_cols - len(row)) for row in parsed_rows]
            
            return jsonify({
                "headers": headers,
                "rows": rows,
                "total_rows": len(rows),
                "file_path": csv_path
            })
        except FileNotFoundError:
            return jsonify({"error": "Report file not found"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return api_bp