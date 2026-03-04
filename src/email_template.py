"""Email template loading and rendering."""
import os
import yaml
from typing import Optional


def load_email_template(config_dir: str = None) -> dict:
    """Load email template from config.
    
    Args:
        config_dir: path to config directory; defaults to ./config
        
    Returns:
        Dict with 'subject' and 'body' keys
    """
    if config_dir is None:
        config_dir = os.path.join(os.getcwd(), "config")
    
    template_path = os.path.join(config_dir, "email_template.yaml")
    
    if not os.path.exists(template_path):
        # return defaults if file doesn't exist
        return {
            "subject": "Viva Engage Member List: {group_name}",
            "body": "Please find attached the member list for {group_name}.",
        }
    
    with open(template_path, "r", encoding="utf-8") as f:
        template = yaml.safe_load(f)
    
    template.setdefault("subject", "Viva Engage Member List: {group_name}")
    template.setdefault("body", "Please find attached the member list for {group_name}.")
    
    return template


def load_override_email_template(config_dir: str = None) -> dict:
    """Load override email template from config.
    
    Used when --email ADDRESS is specified for bulk sending.
    
    Args:
        config_dir: path to config directory; defaults to ./config
        
    Returns:
        Dict with 'subject' and 'body' keys
    """
    if config_dir is None:
        config_dir = os.path.join(os.getcwd(), "config")
    
    template_path = os.path.join(config_dir, "email_template_override.yaml")
    
    if not os.path.exists(template_path):
        # return defaults if file doesn't exist
        return {
            "subject": "Viva Engage Member Lists - {date}",
            "body": "Please find attached the member lists for the following communities:\n\n{groups_list}\n\nTotal Reports: {count}\n\nGenerated on {date}",
        }
    
    with open(template_path, "r", encoding="utf-8") as f:
        template = yaml.safe_load(f)
    
    template.setdefault("subject", "Viva Engage Member Lists - {date}")
    template.setdefault("body", "Please find attached the member lists for the following communities:\n\n{groups_list}\n\nTotal Reports: {count}\n\nGenerated on {date}")
    
    return template


def render_template(
    template: dict,
    group_name: str = "",
    group_handle: str = "",
    date: str = "",
    count: int = 0,
) -> tuple[str, str]:
    """Render email template with group information.
    
    Args:
        template: dict with 'subject' and 'body'
        group_name: display name of the group
        group_handle: handle/ID of the group
        date: generation date string
        count: number of members (optional)
        
    Returns:
        Tuple of (subject, body) strings
    """
    context = {
        "group_name": group_name,
        "group_handle": group_handle,
        "date": date,
        "count": count,
    }
    
    subject = template.get("subject", "").format(**context)
    body = template.get("body", "").format(**context)
    
    return subject, body


def render_override_template(
    template: dict,
    groups_list: str,
    date: str,
    count: int = 0,
) -> tuple[str, str]:
    """Render override email template for bulk sending.
    
    Args:
        template: dict with 'subject' and 'body'
        groups_list: formatted list of group names
        date: generation date string
        count: number of reports
        
    Returns:
        Tuple of (subject, body) strings
    """
    context = {
        "groups_list": groups_list,
        "date": date,
        "count": count,
    }
    
    subject = template.get("subject", "").format(**context)
    body = template.get("body", "").format(**context)
    
    return subject, body
