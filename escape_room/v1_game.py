"""Version 1: the LLM is the entire game master.

The room, the rules and the secret solution all live in the system prompt, and
the complete chat history is sent on every turn. This is deliberately simple
and deliberately fragile; Version 2 replaces it with a deterministic engine.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from escape_room.llm import generate

INTRO = (
    "You wake up on a cold floor inside a locked library. Dusty light falls on a desk, "
    "a bookshelf, a painting and a locked drawer. A door with a four-digit keypad is your "
    "way out.\n\nType what you want to do, for example: examine the bookshelf."
)

SYSTEM_PROMPT = """You are the Game Master of a text escape room. The player wakes up in a locked library.
Room objects: a desk, a bookshelf, a painting, a locked drawer, and a door with a four-digit keypad.
SECRET SOLUTION (reveal only through play):
- Bookshelf: four oddly arranged books carry handwritten numbers 4, 7, 1, 2 (drawer code 4712).
- Desk: a letter says "The shelf speaks in the order of the rainbow."
- Drawer (code 4712) contains a brass key.
- The brass key opens a hidden panel behind the painting, with a paper reading 8305 (door code).
- Door code 8305 opens the exit.
RULES: Describe results in 2-4 sentences, stay in setting, give hints only if asked, and do not reveal
the solution early. When the player opens the door with the correct code, end your message with the
exact token [ESCAPED]."""


def new_game() -> list[dict[str, str]]:
    return [{"role": "assistant", "content": INTRO}]


def to_gemini(chat: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Convert app history to Gemini turns, skipping the assistant-only intro."""
    turns = [message for message in chat if message["role"] in {"user", "assistant"}]
    while turns and turns[0]["role"] != "user":
        turns = turns[1:]
    return [
        {
            "role": "user" if message["role"] == "user" else "model",
            "parts": [{"text": message["content"]}],
        }
        for message in turns
    ]


def take_turn(
    chat: list[dict[str, str]],
    text: str,
    generate_fn: Callable[..., str] = generate,
) -> tuple[list[dict[str, str]], bool]:
    """Append the player message, ask the LLM, and detect the escape token."""
    chat = [*chat, {"role": "user", "content": text}]
    reply = generate_fn(to_gemini(chat), system=SYSTEM_PROMPT)
    escaped = "[ESCAPED]" in reply
    reply = reply.replace("[ESCAPED]", "").strip()
    return [*chat, {"role": "assistant", "content": reply}], escaped
