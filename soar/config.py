from __future__ import annotations
import os
import re
from pathlib import Path
from typing import Any
import yaml
from dotenv import load_dotenv

load_dotenv()

ENV_PATTERN = re.compile(r"^\$\{([A-Za-z0-9_]+)\}$")

def _expand_env(obj: Any) -> Any:
    """Recursively expand ${VAR} tokens from environment variables."""
    if isinstance(obj, dict):
        return {k: _expand_env(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env(v) for v in obj]
    if isinstance(obj, str):
        match = ENV_PATTERN.match(obj.strip())
        if match:
            var_name = match.group(1)
            return os.environ.get(var_name, "")
    return obj

class Config:
    def __init__(self, path: str | Path = "config/config.yaml"):
        self.path = Path(path)
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
        else:
            raw = {}
        self._data = _expand_env(raw)
        # Bring-your-own-keys: secrets.local.yaml (written via the dashboard) wins over env vars
        local_secrets = self.path.parent / "secrets.local.yaml"
        if local_secrets.exists():
            try:
                with local_secrets.open("r", encoding="utf-8") as f:
                    overrides = yaml.safe_load(f) or {}
                merged = dict(self._data.get("secrets") or {})
                merged.update(overrides.get("secrets") or {})
                self._data["secrets"] = merged
            except Exception:
                pass

    def secrets_path(self) -> Path:
        return self.path.parent / "secrets.local.yaml"

    def merge_secrets(self, updates: dict[str, str]) -> dict[str, str]:
        """Store non-empty secret values to secrets.local.yaml and apply to memory. Empty value removes."""
        current = dict(self.get("secrets") or {})
        for k, v in (updates or {}).items():
            if str(v).strip():
                current[k] = str(v).strip()
            else:
                current.pop(k, None)
        self._data["secrets"] = current
        with self.secrets_path().open("w", encoding="utf-8") as f:
            yaml.safe_dump({"secrets": current}, f, default_flow_style=False)
        return current

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self._data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node if node is not None else default

    def set(self, dotted: str, value: Any):
        parts = dotted.split(".")
        node = self._data
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    @property
    def data(self) -> dict[str, Any]:
        return self._data
