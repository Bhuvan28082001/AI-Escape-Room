"""Gradio interface for Version 1 (LLM-only game master)."""

from __future__ import annotations

import gradio as gr

from escape_room.llm import LLMError, generate, is_configured
from escape_room.v1_game import INTRO, new_game, take_turn

STATUS_IDLE = "Version 1 keeps the whole game inside the LLM prompt."
STATUS_ESCAPED = "**You escaped! Press Restart to play again.**"


def _chatbot(value: list[dict], height: int = 430) -> gr.Chatbot:
    try:
        return gr.Chatbot(value=value, type="messages", height=height)
    except TypeError:
        return gr.Chatbot(value=value, height=height)


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="AI Escape Room v1") as demo:
        gr.Markdown(
            "# AI Escape Room (Version 1)\n"
            "The LLM is the Game Master. Find clues, open the drawer and unlock the door.\n\n"
            "Type actions such as *examine the bookshelf*. Version 1 needs a Gemini API key."
        )
        with gr.Row():
            with gr.Column(scale=3):
                bot = _chatbot(new_game())
                box = gr.Textbox(placeholder="What do you do?", show_label=False)
                with gr.Row():
                    send = gr.Button("Send", variant="primary")
                    restart = gr.Button("Restart game")
            with gr.Column(scale=1):
                status = gr.Markdown(STATUS_IDLE)
                gr.Markdown(
                    "**Try:**\n"
                    "- examine the bookshelf\n"
                    "- enter 4712 on the drawer\n"
                    "- use the key on the painting\n"
                    "- enter 8305 on the door"
                )
        done = gr.State(False)

        def on_send(text: str, chat: list[dict], finished: bool):
            if finished:
                return chat, "", finished, STATUS_ESCAPED
            if not text.strip():
                return chat, "", finished, STATUS_IDLE
            try:
                chat, escaped = take_turn(chat, text)
            except LLMError as exc:
                chat = [
                    *chat,
                    {"role": "user", "content": text},
                    {"role": "assistant", "content": f"*Game Master unavailable:* {exc}"},
                ]
                return chat, "", finished, "**LLM error.** Check your `.env` file."
            except Exception:
                chat = [
                    *chat,
                    {"role": "user", "content": text},
                    {
                        "role": "assistant",
                        "content": "*The Game Master is temporarily unavailable. Please try again.*",
                    },
                ]
                return chat, "", finished, "**LLM error.** Please try again."
            return chat, "", escaped, STATUS_ESCAPED if escaped else STATUS_IDLE

        def on_restart():
            return new_game(), "", False, STATUS_IDLE

        send.click(on_send, [box, bot, done], [bot, box, done, status])
        box.submit(on_send, [box, bot, done], [bot, box, done, status])
        restart.click(on_restart, None, [bot, box, done, status])
    return demo


def main() -> None:
    if not is_configured():
        print("Warning: GEMINI_API_KEY is not set. Version 1 needs it to play.")
    build_demo().launch()


if __name__ == "__main__":
    main()
