"""Configuration loading: YAML file + environment overrides."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml

# repo root = .../ambulance-intelligence-system
ROOT = Path(__file__).resolve().parents[3]


def _deep_get(d: Dict[str, Any], dotted: str, default=None):
    cur: Any = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


class Config:
    """Thin, dotted-path accessor over the YAML configuration."""

    def __init__(self, data: Dict[str, Any], path: Path):
        self._data = data
        self.path = path
        self._apply_env_overrides()

    def _apply_env_overrides(self) -> None:
        env_map = {
            "AIS_MODE": "mode",
            "AIS_MODEL_PATH": "model.path",
            "AIS_VIDEO_SOURCE": "video.source",
            "AIS_DATABASE_URL": "database.url",
        }
        for env, dotted in env_map.items():
            val = os.environ.get(env)
            if val:
                self.set(dotted, val)

    # --- access -----------------------------------------------------
    def get(self, dotted: str, default=None):
        return _deep_get(self._data, dotted, default)

    def set(self, dotted: str, value) -> None:
        parts = dotted.split(".")
        cur = self._data
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = value

    def as_dict(self) -> Dict[str, Any]:
        return self._data

    # --- helpers ----------------------------------------------------
    def resolve(self, dotted: str) -> Path:
        """Resolve a configured relative path against the repo root."""
        value = self.get(dotted)
        p = Path(str(value))
        return p if p.is_absolute() else (ROOT / p)

    @property
    def mode(self) -> str:
        return str(self.get("mode", "demo")).lower()


def load_config(path: str | os.PathLike | None = None) -> Config:
    cfg_path = Path(path or os.environ.get("AIS_CONFIG") or (ROOT / "configs/config.yaml"))
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    with open(cfg_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return Config(data, cfg_path)


@lru_cache(maxsize=1)
def get_config() -> Config:
    return load_config()
