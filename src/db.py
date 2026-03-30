import csv
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, List

import jampy_db

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


class DatabaseExecutor:
    def __init__(self, tns: str, profile: str = "oracle_thick_external", **props):
        # build a shared jampy_db client; extra props may include client_folder,
        # lib_dir, config_dir, or any other profile-specific keyword arguments.
        self.client = jampy_db.create(profile, tnsname=tns, **props)

    def run_query(self, query: str) -> List[Any]:
        # execute synchronously; default return_type 'rows' returns list of dicts
        started = time.perf_counter()
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
        try:
            self.client.close()
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
