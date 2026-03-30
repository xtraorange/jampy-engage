"""Service for managing groups and their configurations."""
import glob
import os
import shutil
import stat
import time
from typing import List, Optional

from ..config import load_group_config
from ..group import Group
from ..utils.validation import extract_entra_group_id, validate_group_handle


class GroupService:
    """Service for group management operations."""

    def __init__(self, base_path: str):
        self.base_path = base_path
        self.groups_path = os.path.join(base_path, "groups")

    def discover_groups(self) -> List[Group]:
        """Discover all groups in the groups directory."""
        pattern = os.path.join(self.groups_path, "*")
        folders = [p for p in glob.glob(pattern) if os.path.isdir(p)]
        groups = []

        for folder in folders:
            try:
                groups.append(Group(folder))
            except Exception:
                # Skip folders that don't have valid group.yaml
                pass

        return groups

    def get_group(self, handle: str) -> Optional[Group]:
        """Get a group by handle."""
        groups = self.discover_groups()
        return next((g for g in groups if g.handle == handle), None)

    def create_group(
        self,
        handle: str,
        display_name: str,
        tags: List[str],
        query: Optional[str] = None,
        query_builder: Optional[dict] = None,
        email_recipient: Optional[str] = None,
        output_dir: Optional[str] = None,
        entra_group_link: Optional[str] = None,
    ) -> Group:
        """Create a new group."""
        if not handle or not handle.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Invalid group handle")

        os.makedirs(self.groups_path, exist_ok=True)
        group_dir = os.path.join(self.groups_path, handle)
        if os.path.exists(group_dir):
            raise ValueError("Group already exists")

        os.makedirs(group_dir, exist_ok=True)

        # Create group.yaml
        config = {
            "handle": handle,
            "display_name": display_name,
            "tags": tags,
        }
        if email_recipient:
            config["email_recipient"] = email_recipient
        if output_dir:
            config["output_dir"] = output_dir
        entra_group_id = extract_entra_group_id(entra_group_link or "")
        if entra_group_id:
            config["entra_group_id"] = entra_group_id
        if query_builder:
            config["query_builder"] = query_builder

        import yaml
        group_cfg_path = os.path.join(group_dir, "group.yaml")
        with open(group_cfg_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f)

        # Create override query.sql only if provided.
        if query is not None and query.strip():
            query_path = os.path.join(group_dir, "query.sql")
            with open(query_path, "w", encoding="utf-8") as f:
                f.write(query)

        return Group(group_dir)

    def update_group(
        self,
        group: Group,
        display_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        query: Optional[str] = None,
        query_builder: Optional[dict] = None,
        email_recipient: Optional[str] = None,
        output_dir: Optional[str] = None,
        query_mode: Optional[str] = None,
        entra_group_link: Optional[str] = None,
    ) -> None:
        """Update an existing group."""
        config = group.config.copy()

        if display_name is not None:
            config["display_name"] = display_name
        if tags is not None:
            config["tags"] = tags
        if email_recipient is not None:
            if email_recipient == "":
                config.pop("email_recipient", None)
            else:
                config["email_recipient"] = email_recipient
        if output_dir is not None:
            if output_dir == "":
                config.pop("output_dir", None)
            else:
                config["output_dir"] = output_dir
        if entra_group_link is not None:
            entra_group_id = extract_entra_group_id(entra_group_link)
            if entra_group_id:
                config["entra_group_id"] = entra_group_id
            else:
                config.pop("entra_group_id", None)
        if query_builder is not None:
            if query_builder:
                config["query_builder"] = query_builder
            else:
                config.pop("query_builder", None)
        if query_mode is not None:
            if query_mode in {"builder", "manual"}:
                config["query_mode"] = query_mode
            else:
                config.pop("query_mode", None)

        # Save config
        import yaml
        cfg_path = os.path.join(group.folder, "group.yaml")
        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f)

        # Update override query (empty string removes override file).
        if query is not None:
            if query.strip():
                with open(group.query_file, "w", encoding="utf-8") as f:
                    f.write(query)
            elif os.path.exists(group.query_file):
                os.remove(group.query_file)

    def rename_group(self, group: Group, new_handle: str) -> Group:
        """Rename a group handle, including folder path and config handle value."""
        target = (new_handle or "").strip()
        if not validate_group_handle(target):
            raise ValueError("Invalid group handle")

        current = group.handle
        if target == current:
            return group

        groups = self.discover_groups()
        for candidate in groups:
            if candidate.handle.lower() == target.lower() and candidate.handle.lower() != current.lower():
                raise ValueError("Group already exists")

        old_dir = group.folder
        new_dir = os.path.join(self.groups_path, target)

        old_norm = os.path.normcase(os.path.normpath(old_dir))
        new_norm = os.path.normcase(os.path.normpath(new_dir))

        if old_norm == new_norm:
            # Windows can ignore case-only rename; hop through a temp folder first.
            temp_dir = os.path.join(self.groups_path, f".__rename_tmp__{time.time_ns()}")
            while os.path.exists(temp_dir):
                temp_dir = os.path.join(self.groups_path, f".__rename_tmp__{time.time_ns()}")
            os.rename(old_dir, temp_dir)
            os.rename(temp_dir, new_dir)
        else:
            if os.path.exists(new_dir):
                raise ValueError("Group already exists")
            os.rename(old_dir, new_dir)

        import yaml

        cfg_path = os.path.join(new_dir, "group.yaml")
        cfg = load_group_config(new_dir)
        cfg["handle"] = target
        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f)

        return Group(new_dir)

    def delete_group(self, group: Group) -> None:
        """Delete a group and all its files."""
        def _make_tree_writable(path: str) -> None:
            if not os.path.exists(path):
                return
            for root, dirs, files in os.walk(path):
                for name in files + dirs:
                    entry = os.path.join(root, name)
                    try:
                        os.chmod(entry, stat.S_IWRITE)
                    except Exception:
                        pass
            try:
                os.chmod(path, stat.S_IWRITE)
            except Exception:
                pass

        def _onrmerror(func, path, exc_info):
            # Retry once after clearing read-only attributes.
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception:
                # Keep original failure behavior so caller can retry with backoff.
                pass

        if not os.path.exists(group.folder):
            return

        last_exc: Optional[Exception] = None
        for attempt in range(10):
            _make_tree_writable(group.folder)
            try:
                shutil.rmtree(group.folder, onerror=_onrmerror)
            except (PermissionError, OSError) as exc:
                last_exc = exc

            if not os.path.exists(group.folder):
                return

            # Transient locks (OneDrive/AV indexing) are common on Windows.
            time.sleep(0.25 * (attempt + 1))

        remaining_sample = []
        try:
            for root, dirs, files in os.walk(group.folder):
                for name in files + dirs:
                    remaining_sample.append(os.path.join(root, name))
                    if len(remaining_sample) >= 5:
                        break
                if len(remaining_sample) >= 5:
                    break
        except Exception:
            remaining_sample = []

        detail = ""
        if last_exc is not None:
            detail = f" Last error: {last_exc}"
        if remaining_sample:
            detail += f" Remaining entries: {remaining_sample}"
        raise Exception(f"Failed to delete group folder.{detail}")

    def get_all_tags(self) -> List[str]:
        """Get all unique tags across all groups."""
        groups = self.discover_groups()
        tags = set()
        for group in groups:
            tags.update(group.tags)
        return sorted(tags)

    def add_tag_to_groups(self, tag_name: str, group_handles: List[str]) -> None:
        """Add a tag to multiple groups."""
        groups = self.discover_groups()
        import yaml

        for group in groups:
            if group.handle in group_handles and tag_name not in group.tags:
                group.config["tags"] = group.config.get("tags", []) + [tag_name]
                cfg_path = os.path.join(group.folder, "group.yaml")
                with open(cfg_path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(group.config, f)

    def remove_tag_from_all_groups(self, tag_name: str) -> None:
        """Remove a tag from all groups that have it."""
        groups = self.discover_groups()
        import yaml

        for group in groups:
            if tag_name in group.tags:
                group.config["tags"] = [t for t in group.config.get("tags", []) if t != tag_name]
                cfg_path = os.path.join(group.folder, "group.yaml")
                with open(cfg_path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(group.config, f)