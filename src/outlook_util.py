"""Outlook integration for sending emails via the Outlook client."""
from typing import Optional

try:
    import win32com.client
    OUTLOOK_AVAILABLE = True
except ImportError:
    OUTLOOK_AVAILABLE = False


def send_via_outlook(
    recipient: str,
    subject: str,
    body: str,
    csv_file: str = None,
    auto_send: bool = False,
) -> bool:
    """Send an email via the Outlook client.

    Args:
        recipient: recipient email address
        subject: email subject
        body: email body text
        csv_file: optional path to CSV file to attach
        auto_send: if True, automatically send email; if False, leave open for review

    Returns:
        True if successful, False otherwise.
    """
    if not OUTLOOK_AVAILABLE:
        print("Error: pywin32 is not installed. Cannot use Outlook integration.")
        return False

    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)  # 0 = olMailItem
        mail.To = recipient
        mail.Subject = subject
        mail.Body = body

        if csv_file:
            try:
                mail.Attachments.Add(csv_file)
            except Exception as e:
                print(f"Warning: could not attach {csv_file}: {e}")

        if auto_send:
            mail.Send()
            return True
        else:
            # Display the email for user review/editing
            mail.Display()
            return True

    except Exception as e:
        print(f"Error sending email via Outlook to {recipient}: {e}")
        return False
