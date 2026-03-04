import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional


def send_email(
    smtp_server: str,
    smtp_port: int,
    smtp_from: str,
    recipient: str,
    subject: str,
    body: str,
    csv_file: str = None,
    use_tls: bool = False,
) -> bool:
    """Send an email with optional CSV attachment.

    Args:
        smtp_server: SMTP server hostname
        smtp_port: SMTP port number
        smtp_from: sender email address
        recipient: recipient email address
        subject: email subject
        body: email body text
        csv_file: optional path to CSV file to attach
        use_tls: whether to use TLS

    Returns:
        True if successful, False otherwise.
    """
    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_from
        msg["To"] = recipient
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))

        if csv_file:
            try:
                with open(csv_file, "rb") as attachment:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment.read())
                encoders.encode_base64(part)
                filename = csv_file.split("\\")[-1]  # get basename
                part.add_header("Content-Disposition", f"attachment; filename= {filename}")
                msg.attach(part)
            except Exception as e:
                print(f"Warning: could not attach {csv_file}: {e}")

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            if use_tls:
                server.starttls()
            server.sendmail(smtp_from, recipient, msg.as_string())

        return True
    except Exception as e:
        print(f"Error sending email to {recipient}: {e}")
        return False
