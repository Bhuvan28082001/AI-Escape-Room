"""Configuration loading and name resolution for Version 2."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "game_v2.json"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with config_path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    required = {"objects", "items", "locks", "uses"}
    missing = required.difference(config)
    if missing:
        raise ValueError(f"Game config is missing sections: {sorted(missing)}")
    return config


def normalise(text: Any) -> str:
    value = str(text or "").strip().lower()
    value = value.replace("_", " ").replace("-", " ")
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"^(the|a|an)\s+", "", value)
    return value


def build_alias_index(entries: dict[str, dict[str, Any]]) -> dict[str, str]:
    index: dict[str, str] = {}
    for canonical, details in entries.items():
        for name in [canonical, *details.get("aliases", [])]:
            index[normalise(name)] = canonical
    return index


def match_alias(text: Any, index: dict[str, str]) -> str | None:
    value = normalise(text)
    if not value:
        return None
    if value in index:
        return index[value]
    for phrase in sorted(index, key=len, reverse=True):
        pattern = rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])"
        if re.search(pattern, value):
            return index[phrase]
    return None
