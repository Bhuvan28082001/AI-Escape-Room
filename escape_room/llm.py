"""Shared Gemini client used by both versions of the game."""

from __future__ import annotations

import os
import time
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

DEFAULT_MODEL = "gemini-2.5-flash"
_client: genai.Client | None = None
_client_key: str | None = None


class LLMError(RuntimeError):
    """Raised when the Gemini API is not configured or the request fails."""


def get_api_key() -> str | None:
    return os.getenv("GEMINI_API_KEY") or None


def is_configured() -> bool:
    return bool(get_api_key())


def get_model_name() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_MODEL)


def _get_client() -> genai.Client:
    global _client, _client_key
    key = get_api_key()
    if not key:
        raise LLMError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or run Version 2 without the LLM (it falls back to offline mode)."
        )
    if _client is None or _client_key != key:
        _client = genai.Client(api_key=key)
        _client_key = key
    return _client


def generate(
    contents: Any,
    system: str | None = None,
    json_mode: bool = False,
    temperature: float = 0.7,
    retries: int = 1,
) -> str:
    """Send a request to Gemini and return plain text.

    ``contents`` is a prompt string or a Gemini conversation list. The function
    retries once on a transient failure and raises ``LLMError`` with a safe
    message if the request still fails.
    """
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        response_mime_type="application/json" if json_mode else None,
    )
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = _get_client().models.generate_content(
                model=get_model_name(), contents=contents, config=config
            )
            return response.text or ""
        except Exception as exc:  # noqa: BLE001 - the UI needs a friendly error
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise LLMError(
        "The Gemini request failed. Check your API key, model name and network connection."
    ) from last_error
