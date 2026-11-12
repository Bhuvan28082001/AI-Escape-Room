"""Structured game state for Version 2."""

from __future__ import annotations

from typing import Any


def new_state() -> dict[str, Any]:
    return {
        "inventory": [],
        "examined": [],
        "taken": [],
        "flags": {},
        "escaped": False,
        "turns": 0,
        "log": [],
    }
