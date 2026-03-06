"""Input validation utilities."""


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