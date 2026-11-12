"""Version 2 game loop: parse -> validate -> update state -> narrate."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from escape_room.v2.config import load_config
from escape_room.v2.engine import ActionResult, GameEngine
from escape_room.v2.narrator import narrate
from escape_room.v2.parser import parse_intent


@dataclass
class Turn:
    intent: dict[str, Any]
    result: ActionResult
    narration: str


class EscapeRoomGame:
    def __init__(
        self,
        config: dict[str, Any] | None = None,
        llm: Callable[..., str] | None = None,
    ):
        self.config = config or load_config()
        self.llm = llm
        self.engine = GameEngine(self.config)

    def reset(self) -> None:
        self.engine.reset()

    def play(self, text: str) -> Turn:
        intent = parse_intent(text, self.config, self.llm)
        result = self.engine.apply(intent)
        narration = narrate(text, result, self.config, self.llm)
        return Turn(intent=intent, result=result, narration=narration)

    def status(self) -> dict[str, Any]:
        return self.engine.status()

    @property
    def state(self) -> dict[str, Any]:
        return self.engine.state
