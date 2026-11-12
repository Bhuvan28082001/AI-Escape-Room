from __future__ import annotations

from escape_room.v1_game import new_game, take_turn, to_gemini


def test_new_game_starts_with_one_assistant_intro() -> None:
    chat = new_game()
    assert len(chat) == 1
    assert chat[0]["role"] == "assistant"
    assert "locked library" in chat[0]["content"]


def test_to_gemini_skips_intro_and_maps_roles() -> None:
    chat = [
        {"role": "assistant", "content": "intro"},
        {"role": "user", "content": "look around"},
        {"role": "assistant", "content": "a desk"},
        {"role": "user", "content": "open the door"},
    ]
    assert to_gemini(chat) == [
        {"role": "user", "parts": [{"text": "look around"}]},
        {"role": "model", "parts": [{"text": "a desk"}]},
        {"role": "user", "parts": [{"text": "open the door"}]},
    ]


def test_take_turn_detects_and_strips_escape_token() -> None:
    captured = {}

    def fake_generate(contents, system=None, **kwargs):
        captured["contents"] = contents
        captured["system"] = system
        return "The door swings open. [ESCAPED]"

    chat, escaped = take_turn(new_game(), "enter 8305 on the door", generate_fn=fake_generate)

    assert escaped is True
    assert chat[-1] == {"role": "assistant", "content": "The door swings open."}
    assert chat[-2] == {"role": "user", "content": "enter 8305 on the door"}
    assert captured["contents"][-1] == {
        "role": "user",
        "parts": [{"text": "enter 8305 on the door"}],
    }
    assert "4712" in captured["system"]
    assert "8305" in captured["system"]
