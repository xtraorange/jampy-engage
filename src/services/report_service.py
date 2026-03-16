"""Core report generation service."""
import os
import re
from datetime import datetime
from time import perf_counter
from typing import List, Optional

from ..config import load_general_config
from ..db import DatabaseExecutor, ProgressTracker
from ..group import Group
from .email_service import EmailService


_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1F]')


def _safe_filename_component(value: str, default: str = "unnamed") -> str:
    """Normalize user-facing text into a Windows-safe filename component."""
    cleaned = _INVALID_FILENAME_CHARS.sub("-", str(value or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned or default


def _build_output_filename(folder: str, handle: str, display_name: str, date_str: str) -> str:
    """Build a safe CSV filename while keeping full path under common Windows limits."""
    safe_handle = _safe_filename_component(handle, default="group")
    safe_display = _safe_filename_component(display_name or handle, default=safe_handle)
    max_path = 240  # keep headroom under traditional Windows MAX_PATH

    def _compose(h: str, d: str) -> str:
        return f"{h} ({d}) - {date_str}.csv"

    fname = _compose(safe_handle, safe_display)
    fullpath = os.path.join(folder, fname)
    if len(fullpath) <= max_path:
        return fname

    overflow = len(fullpath) - max_path
    if overflow > 0 and len(safe_display) > 12:
        trim = min(overflow, len(safe_display) - 12)
        safe_display = safe_display[:-trim].rstrip(" ._-") or safe_display[:12]

    fname = _compose(safe_handle, safe_display)
    fullpath = os.path.join(folder, fname)
    overflow = len(fullpath) - max_path
    if overflow > 0 and len(safe_handle) > 12:
        trim = min(overflow, len(safe_handle) - 12)
        safe_handle = safe_handle[:-trim].rstrip(" ._-") or safe_handle[:12]

    fname = _compose(safe_handle, safe_display)
    return fname


class ReportService:
    """Service for generating reports and managing the processing workflow."""

    def __init__(self, config: dict):
        self.config = config
        self.email_service = EmailService(config)

    def process_groups(
        self,
        groups: List[Group],
        should_email: bool = False,
        override_email: Optional[str] = None,
        progress_callback: Optional[callable] = None,
        tracker: Optional[ProgressTracker] = None,
        return_details: bool = False,
    ) -> List[str]:
        """Process multiple groups and generate reports.

        Args:
            groups: List of groups to process
            should_email: Whether to send individual emails
            override_email: Email address for bulk sending (overrides individual emails)
            progress_callback: Optional callback for progress updates
            tracker: Optional ProgressTracker instance for UI integration

        Returns:
            List of generated CSV file paths
        """
        executor = DatabaseExecutor(self.config.get("oracle_tns"))
        max_workers = self.config.get("max_workers") or os.cpu_count() or 4
        if tracker is None:
            tracker = ProgressTracker(len(groups))
        csv_files = []
        group_run_details = {}

        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = []
                for idx, group in enumerate(groups, start=1):
                    tracker.update(group.handle, "queued")
                    future = pool.submit(
                        self._process_single_group,
                        group,
                        executor,
                        tracker,
                        should_email,
                        override_email,
                        idx,
                        len(groups)
                    )
                    futures.append(future)

                for future in as_completed(futures):
                    try:
                        result = future.result()
                        if result:
                            csv_path = result.get("csv_path")
                            group_result = {
                                "duration_seconds": result["duration_seconds"],
                                "success": bool(csv_path),
                                "csv_path": csv_path,
                            }
                            group_run_details[result["handle"]] = group_result
                            # Store in tracker for UI access
                            if tracker:
                                tracker.set_result(result["handle"], group_result)
                        if csv_path:
                            csv_files.append(csv_path)
                            if progress_callback:
                                progress_callback(csv_path)
                    except Exception as e:
                        print(f"Error in group processing task: {e}")

            # Send bulk email if override email is specified
            if override_email and csv_files:
                self._send_bulk_email(override_email, csv_files, groups)

        finally:
            try:
                executor.close()
            except Exception:
                pass

        if return_details:
            return {
                "csv_files": csv_files,
                "group_run_details": group_run_details,
            }

        return csv_files

    def _process_single_group(
        self,
        group: Group,
        executor: DatabaseExecutor,
        tracker: ProgressTracker,
        should_email: bool,
        override_email: Optional[str],
        job_num: int,
        job_total: int
    ) -> Optional[str]:
        """Process a single group.

        Returns:
            Path to generated CSV file, or None if failed
        """
        handle = group.handle
        started = perf_counter()
        tracker.update(handle, f"generating member list ({job_num}/{job_total})")

        try:
            # Read and execute query
            tracker.update(handle, "querying database")
            query = group.read_query()
            rows = executor.run_query(query)
            tracker.update(handle, f"fetched {len(rows)} rows")

            # Process email addresses
            emails = self._extract_emails(rows)
            rows = emails

            # Prepare output
            out_base = self.config.get("output_dir")
            folder = group.output_path(out_base)
            os.makedirs(folder, exist_ok=True)

            date_str = datetime.now().strftime("%y-%m-%d")
            fname = _build_output_filename(folder, handle, group.display_name, date_str)
            fullpath = os.path.join(folder, fname)

            # Write CSV
            tracker.update(handle, "writing CSV")
            executor.write_csv(rows, None, fullpath)
            tracker.update(handle, f"written {os.path.basename(fullpath)}")

            # Send individual email if requested and not using bulk override
            if should_email and not override_email:
                tracker.update(handle, "sending email")
                self._send_group_email(group, fullpath, len(rows), date_str)

            return {
                "handle": handle,
                "csv_path": fullpath,
                "duration_seconds": round(perf_counter() - started, 3),
            }

        except Exception as e:
            tracker.update(handle, f"failed: {e}")
            return {
                "handle": handle,
                "csv_path": None,
                "duration_seconds": round(perf_counter() - started, 3),
            }
        finally:
            tracker.increment(handle)

    def _extract_emails(self, rows: List) -> List[tuple]:
        """Extract and normalize email addresses from query results."""
        emails = []
        for row in rows:
            email = None
            if isinstance(row, dict):
                # Try to find username column
                for key, value in row.items():
                    if key.lower() == "username" and isinstance(value, str):
                        email = value
                        break
            else:
                # Assume first column is username
                if row and isinstance(row[0], str):
                    email = row[0]

            if email is None:
                continue

            # Add domain if not present
            if not email.lower().endswith("@fastenal.com"):
                email = f"{email}@fastenal.com"

            emails.append((email,))

        return emails

    def _send_group_email(
        self,
        group: Group,
        csv_file: str,
        row_count: int,
        date_str: str
    ) -> None:
        """Send email for a single group."""
        recipient = group.config.get("email_recipient") or self.config.get("email_recipient")
        if not recipient:
            return

        auto_send = self.config.get("outlook_auto_send", False)
        self.email_service.send_group_email(
            recipient=recipient,
            csv_file=csv_file,
            group_name=group.display_name,
            group_handle=group.handle,
            date_str=date_str,
            row_count=row_count,
            auto_send=auto_send
        )

    def _send_bulk_email(
        self,
        recipient: str,
        csv_files: List[str],
        groups: List[Group]
    ) -> None:
        """Send bulk email with all generated CSVs."""
        date_str = datetime.now().strftime("%y-%m-%d")
        groups_list = "\n".join([f"  - {os.path.basename(f)}" for f in csv_files])

        self.email_service.send_bulk_email(
            recipient=recipient,
            csv_files=csv_files,
            groups_list=groups_list,
            date_str=date_str,
            count=len(groups)
        )