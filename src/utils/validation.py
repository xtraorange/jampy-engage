"""Input validation utilities."""

import re


_GUID_RE = re.compile(
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)


def extract_entra_group_id(value: str) -> str:
    """Extract and normalize a groupId GUID from a raw value or Entra URL.

    Returns an empty string when no valid GUID is found.
    """
    raw = (value or "").strip()
    if not raw:
        return ""

    match = _GUID_RE.search(raw)
    if not match:
        return ""
    return match.group(1).lower()


def build_entra_members_url(group_id: str) -> str:
    """Build the Entra members page URL for a given group ID."""
    normalized = extract_entra_group_id(group_id)
    if not normalized:
        return ""
    return (
        "https://entra.microsoft.com/?pwa=1#view/Microsoft_AAD_IAM/"
        f"GroupDetailsMenuBlade/~/Members/groupId/{normalized}/menuId/"
    )


def validate_email(email: str) -> bool:
    """Validate email address format."""
    if not email or "@" not in email:
        return False
    local, domain = email.split("@", 1)
    return bool(local and domain and "." in domain)


def validate_group_handle(handle: str) -> bool:
    """Validate group handle (alphanumeric, underscore, dash only)."""
    if not handle:
        return False
    return handle.replace("_", "").replace("-", "").isalnum()


def validate_tag_name(tag: str) -> bool:
    """Validate tag name (no special characters that could cause issues)."""
    if not tag or not tag.strip():
        return False
    # Allow alphanumeric, spaces, underscores, dashes
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-")
    return all(c in allowed_chars for c in tag)


def sanitize_sql_input(value: str) -> str:
    """Sanitize SQL input by escaping single quotes."""
    if isinstance(value, str):
        return value.replace("'", "''")
    return str(value)