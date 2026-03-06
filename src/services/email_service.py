"""Unified email service for sending reports via SMTP or Outlook."""
import os
from typing import List, Optional

from ..email_util import send_email as smtp_send_email
from ..outlook_util import send_via_outlook, OUTLOOK_AVAILABLE
from ..email_template import load_email_template, load_override_email_template, render_template, render_override_template


class EmailService:
    """Unified service for sending emails with CSV attachments."""

    def __init__(self, config: dict):
        self.config = config
        self.email_method = config.get("email_method", "smtp")

    def send_group_email(
        self,
        recipient: str,
        csv_file: str,
        group_name: str,
        group_handle: str,
        date_str: str,
        row_count: int = 0,
        auto_send: bool = False
    ) -> bool:
        """Send email for a single group.

        Args:
            recipient: Email recipient
            csv_file: Path to CSV file to attach
            group_name: Display name of the group
            group_handle: Handle/ID of the group
            date_str: Date string for template
            row_count: Number of members
            auto_send: Whether to auto-send Outlook emails

        Returns:
            True if successful, False otherwise
        """
        # Load and render template
        template = load_email_template()
        subject, body = render_template(
            template,
            group_name=group_name,
            group_handle=group_handle,
            date=date_str,
            count=row_count,
        )

        return self._send_email(
            recipient=recipient,
            subject=subject,
            body=body,
            csv_file=csv_file,
            auto_send=auto_send
        )

    def send_bulk_email(
        self,
        recipient: str,
        csv_files: List[str],
        groups_list: str,
        date_str: str,
        count: int
    ) -> bool:
        """Send bulk email with multiple CSV attachments.

        Args:
            recipient: Email recipient
            csv_files: List of CSV file paths
            groups_list: Formatted list of group names
            date_str: Date string
            count: Number of groups

        Returns:
            True if successful, False otherwise
        """
        # Load and render override template
        template = load_override_email_template()
        subject, body = render_override_template(
            template,
            groups_list=groups_list,
            date=date_str,
            count=count,
        )

        if self.email_method == "outlook":
            return self._send_bulk_outlook(recipient, subject, body, csv_files)
        else:
            return self._send_bulk_smtp(recipient, subject, body, csv_files)

    def _send_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        csv_file: str,
        auto_send: bool = False
    ) -> bool:
        """Send a single email with one CSV attachment."""
        if self.email_method == "outlook":
            if not OUTLOOK_AVAILABLE:
                print("Outlook integration not available; install pywin32 or use smtp.")
                return False
            return send_via_outlook(
                recipient=recipient,
                subject=subject,
                body=body,
                csv_file=csv_file,
                auto_send=auto_send
            )
        else:
            # SMTP method
            smtp_server = self.config.get("smtp_server")
            smtp_port = self.config.get("smtp_port", 25)
            smtp_from = self.config.get("smtp_from", "reports@fastenal.com")
            use_tls = self.config.get("smtp_use_tls", False)

            if not smtp_server:
                print("SMTP not configured; cannot send email")
                return False

            return smtp_send_email(
                smtp_server=smtp_server,
                smtp_port=smtp_port,
                smtp_from=smtp_from,
                recipient=recipient,
                subject=subject,
                body=body,
                csv_file=csv_file,
                use_tls=use_tls,
            )

    def _send_bulk_outlook(
        self,
        recipient: str,
        subject: str,
        body: str,
        csv_files: List[str]
    ) -> bool:
        """Send multiple CSVs via Outlook (one email with multiple attachments)."""
        if not OUTLOOK_AVAILABLE:
            print("Outlook integration not available; install pywin32 or use smtp.")
            return False

        auto_send = self.config.get("outlook_auto_send", False)
        success = True

        # For Outlook, we need to send separate emails since the current implementation
        # doesn't support multiple attachments in one email
        for i, csv_file in enumerate(csv_files):
            current_subject = subject if i == 0 else f"[Part {i + 1}] {subject}"
            current_body = body if i == 0 else ""

            s = send_via_outlook(
                recipient=recipient,
                subject=current_subject,
                body=current_body,
                csv_file=csv_file,
                auto_send=auto_send,
            )
            success = success and s

        return success

    def _send_bulk_smtp(
        self,
        recipient: str,
        subject: str,
        body: str,
        csv_files: List[str]
    ) -> bool:
        """Send multiple CSVs via SMTP (one email with multiple attachments)."""
        from ..email_util import send_email

        smtp_server = self.config.get("smtp_server")
        smtp_port = self.config.get("smtp_port", 25)
        smtp_from = self.config.get("smtp_from", "reports@fastenal.com")
        use_tls = self.config.get("smtp_use_tls", False)

        if not smtp_server:
            print("SMTP not configured; cannot send bulk email")
            return False

        # Send one email with multiple attachments
        success = True
        for i, csv_file in enumerate(csv_files):
            current_body = body if i == 0 else f"(attachment {i + 1})"
            s = send_email(
                smtp_server=smtp_server,
                smtp_port=smtp_port,
                smtp_from=smtp_from,
                recipient=recipient,
                subject=subject,
                body=current_body,
                csv_file=csv_file,
                use_tls=use_tls,
            )
            success = success and s

        return success