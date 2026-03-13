"""File and directory utilities."""
import os
import shutil
import zipfile
from io import BytesIO
from datetime import datetime
from typing import List


def ensure_directory(path: str) -> None:
    """Ensure a directory exists, creating it if necessary."""
    os.makedirs(path, exist_ok=True)


def safe_delete_directory(path: str) -> None:
    """Safely delete a directory, handling Windows file permissions."""
    import stat

    def _onrmerror(func, path, exc_info):
        try:
            os.chmod(path, stat.S_I_WRITE)
            func(path)
        except Exception:
            pass

    # Walk and chmod for Windows
    for root, dirs, files in os.walk(path):
        for name in files + dirs:
            filepath = os.path.join(root, name)
            try:
                os.chmod(filepath, stat.S_I_WRITE)
            except Exception:
                pass

    # Try removing up to a few times
    import time
    for attempt in range(4):
        try:
            shutil.rmtree(path, onerror=_onrmerror)
            break
        except PermissionError:
            time.sleep(0.5)

    # Final check
    if os.path.exists(path):
        raise Exception(f"Failed to delete directory: {path}")


def create_backup_zip(base_path: str) -> BytesIO:
    """Create a zip backup of config and groups."""
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add config files
        config_path = os.path.join(base_path, "config")
        for filename in os.listdir(config_path):
            if filename.endswith((".yaml", ".yml")):
                file_path = os.path.join(config_path, filename)
                zf.write(file_path, os.path.join("config", filename))

        # Add groups
        groups_path = os.path.join(base_path, "groups")
        if os.path.exists(groups_path):
            for root, dirs, files in os.walk(groups_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, base_path)
                    zf.write(file_path, arcname)

    zip_buffer.seek(0)
    return zip_buffer


def get_backup_filename() -> str:
    """Generate a backup filename with timestamp."""
    return f'viva-engage-tools-backup-{datetime.now().strftime("%Y%m%d-%H%M%S")}.zip'


def validate_group_handle(handle: str) -> bool:
    """Validate a group handle format."""
    if not handle:
        return False
    return handle.replace("_", "").replace("-", "").isalnum()