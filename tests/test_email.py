import pytest
from unittest.mock import patch, MagicMock

from src.email_util import send_email
from src.generate_reports import _email_report
from src.group import Group
import tempfile
import os


def test_send_email_success(monkeypatch):
    """Test successful email sending."""
    mock_smtp = MagicMock()
    monkeypatch.setattr("smtplib.SMTP", MagicMock(return_value=mock_smtp.__enter__.return_value))
    
    success = send_email(
        smtp_server="mail.test.com",
        smtp_port=25,
        smtp_from="sender@test.com",
        recipient="user@test.com",
        subject="Test",
        body="Test body",
    )
    
    assert success is True


def test_send_email_with_attachment(monkeypatch, tmp_path):
    """Test email with CSV attachment."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("email1@test.com\nemail2@test.com\n")
    
    mock_smtp = MagicMock()
    mock_context = MagicMock()
    mock_context.__enter__.return_value = mock_smtp
    mock_context.__exit__.return_value = False
    monkeypatch.setattr("smtplib.SMTP", MagicMock(return_value=mock_context))
    
    success = send_email(
        smtp_server="mail.test.com",
        smtp_port=25,
        smtp_from="sender@test.com",
        recipient="user@test.com",
        subject="Test",
        body="Test body",
        csv_file=str(csv_file),
    )
    
    assert success is True
    # verify sendmail was called
    assert mock_smtp.sendmail.called


def test_email_report_missing_config(tmp_path):
    """Test _email_report with missing recipient config."""
    tracker = MagicMock()
    
    # create minimal group
    gfolder = tmp_path / "test"
    gfolder.mkdir()
    with open(gfolder / "group.yaml", "w") as f:
        import yaml
        yaml.safe_dump({"handle": "test", "display_name": "Test"}, f)
    with open(gfolder / "query.sql", "w") as f:
        f.write("select 1")
    
    group = Group(str(gfolder))
    general_cfg = {"output_dir": str(tmp_path)}  # no email config
    
    _email_report(group, general_cfg, "/fake/file.csv", tracker)
    
    # verify tracker was updated to indicate skip
    tracker.update.assert_called()
    call_args = str(tracker.update.call_args)
    assert "skipped" in call_args.lower()


def test_email_report_with_recipient(tmp_path, monkeypatch):
    """Test _email_report actually sends email when recipient is configured."""
    mock_send = MagicMock(return_value=True)
    monkeypatch.setattr("src.email_util.send_email", mock_send)
    
    tracker = MagicMock()
    
    # create minimal group
    gfolder = tmp_path / "test"
    gfolder.mkdir()
    with open(gfolder / "group.yaml", "w") as f:
        import yaml
        yaml.safe_dump(
            {"handle": "test", "display_name": "Test Group", "email_recipient": "admin@test.com"},
            f,
        )
    with open(gfolder / "query.sql", "w") as f:
        f.write("select 1")
    
    group = Group(str(gfolder))
    general_cfg = {
        "output_dir": str(tmp_path),
        "smtp_server": "mail.test.com",
        "smtp_port": 25,
        "smtp_from": "reports@test.com",
    }
    csv_file = str(tmp_path / "test.csv")
    
    _email_report(group, general_cfg, csv_file, tracker)
    
    # verify send_email was called
    assert mock_send.called
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["recipient"] == "admin@test.com"
    assert call_kwargs["csv_file"] == csv_file
