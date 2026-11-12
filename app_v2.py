"""Gradio interface for Version 2 (deterministic engine + LLM language layer)."""

from __future__ import annotations

from typing import Any

import gradio as gr

from escape_room.llm import generate, is_configured
from escape_room.v2.game import EscapeRoomGame


def _new_game() -> EscapeRoomGame:
    return EscapeRoomGame(llm=generate if is_configured() else None)


def _intro(game: EscapeRoomGame) -> list[dict[str, str]]:
    return [{"role": "assistant", "content": game.config["intro"]}]


def _chatbot(value: list[dict], height: int = 430) -> gr.Chatbot:
    try:
        return gr.Chatbot(value=value, type="messages", height=height)
    except TypeError:
        return gr.Chatbot(value=value, height=height)


def _status(state: dict[str, Any]) -> str:
    inventory = ", ".join(state["inventory"]) or "empty"
    escaped = "yes" if state["escaped"] else "no"
    return (
        f"**Inventory:** {inventory}  \n"
        f"**Drawer:** {state['drawer']}  \n"
        f"**Panel:** {state['panel']}  \n"
        f"**Door:** {state['door']}  \n"
        f"**Escaped:** {escaped}  \n"
        f"**Turns:** {state['turns']}"
    )


def build_demo() -> gr.Blocks:
    initial_game = _new_game()
    with gr.Blocks(title="AI Escape Room v2") as demo:
        gr.Markdown(
            "# AI Escape Room (Version 2)\n"
            "Python owns the rules, the inventory and the codes. The LLM only classifies "
            "your intent and narrates verified outcomes.\n\n"
            "Try *examine the bookshelf*, *inventory*, or *hint*. "
            "The game works offline with a deterministic parser and narrator."
        )
        with gr.Row():
            with gr.Column(scale=3):
                bot = _chatbot(_intro(initial_game))
                box = gr.Textbox(placeholder="What do you do?", show_label=False)
                with gr.Row():
                    send = gr.Button("Send", variant="primary")
                    inventory = gr.Button("Inventory")
                    hint = gr.Button("Hint")
                    restart = gr.Button("Restart game")
            with gr.Column(scale=1):
                status = gr.Markdown(_status(initial_game.status()))
                gr.Markdown(
                    "**Game rules**\n"
                    "- Only collected items can be used.\n"
                    "- A lock needs the right code and the relevant clue.\n"
                    "- The door needs the paper from the hidden panel.\n\n"
                    "**Try:**\n"
                    "- examine the bookshelf\n"
                    "- examine the books\n"
                    "- enter 4712 on the drawer\n"
                    "- use the key on the painting\n"
                    "- take the paper\n"
                    "- enter 8305 on the door"
                )
        game_state = gr.State(initial_game)

        def on_send(text: str, chat: list[dict], game: EscapeRoomGame):
            if not text.strip():
                return chat, "", game, _status(game.status())
            try:
                turn = game.play(text)
                reply = turn.narration
            except Exception:
                reply = "*The Game Master hit an unexpected problem. No game state changed.*"
                return (
                    chat + [{"role": "user", "content": text}, {"role": "assistant", "content": reply}],
                    "",
                    game,
                    _status(game.status()),
                )
            if game.state["escaped"]:
                reply = f"{reply}\n\n**You escaped! Press Restart to play again.**"
            chat = [
                *chat,
                {"role": "user", "content": text},
                {"role": "assistant", "content": reply},
            ]
            return chat, "", game, _status(game.status())

        def on_restart():
            game = _new_game()
            return _intro(game), "", game, _status(game.status())

        send.click(on_send, [box, bot, game_state], [bot, box, game_state, status])
        box.submit(on_send, [box, bot, game_state], [bot, box, game_state, status])
        inventory.click(
            lambda chat, game: on_send("inventory", chat, game),
            [bot, game_state],
            [bot, box, game_state, status],
        )
        hint.click(
            lambda chat, game: on_send("hint", chat, game),
            [bot, game_state],
            [bot, box, game_state, status],
        )
        restart.click(on_restart, None, [bot, box, game_state, status])
    return demo


def main() -> None:
    if not is_configured():
        print("GEMINI_API_KEY not set: running Version 2 in offline mode (regex parser + narrator).")
    build_demo().launch()


if __name__ == "__main__":
    main()
