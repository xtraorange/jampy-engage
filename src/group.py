import os
from typing import List

from .config import load_group_config


class Group:
    def __init__(self, folder: str):
        self.folder = folder
        self.config = load_group_config(folder)
        self.handle = self.config["handle"]
        self.display_name = self.config.get("display_name")
        self.tags = set(self.config.get("tags", []))
        self.query_file = os.path.join(folder, "query.sql")

    def read_query(self) -> str:
        with open(self.query_file, "r", encoding="utf-8") as f:
            return f.read()

    def output_path(self, base_output: str) -> str:
        # groups can override their own output_dir in config
        override = self.config.get("output_dir")
        if override:
            return override
        return os.path.join(base_output, self.handle)

    def matches(self, names: List[str] = None, tags: List[str] = None) -> bool:
        if names:
            if self.handle in names:
                return True
        if tags:
            if self.tags.intersection(tags):
                return True
        return False
