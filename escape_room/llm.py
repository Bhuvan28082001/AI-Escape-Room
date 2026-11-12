"""Shared Gemini client used by both versions of the game."""

from __future__ import annotations

import os
import re
import time
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

DEFAULT_MODEL = "gemini-3.8-flash"
FALLBACK_MODELS = (
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
)
RETRYABLE_CODES = {408, 429, 500, 502, 503, 504}
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


def get_model_candidates() -> list[str]:
    configured = os.getenv("GEMINI_FALLBACK_MODELS")
    fallbacks = (
        tuple(model.strip() for model in configured.split(",") if model.strip())
        if configured
        else FALLBACK_MODELS
    )
    candidates = [get_model_name(), *fallbacks, DEFAULT_MODEL]
    unique: list[str] = []
    for model in candidates:
        if model and model not in unique:
            unique.append(model)
    return unique


def _get_client() -> genai.Client:
    global _client, _client_key
    key = get_api_key()
    if not key:
        raise LLMError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or run Version 2 without the LLM (it falls back to offline mode)."
        )
    if _client is None or _client_key != key:
        _client = genai.Client(
            api_key=key,
            http_options=types.HttpOptions(timeout=20_000),
        )
        _client_key = key
    return _client


def _status_code(exc: Exception) -> int | None:
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    match = re.search(r"\b([45]\d{2})\b", str(exc))
    return int(match.group(1)) if match else None


def _error_summary(exc: Exception) -> str:
    text = " ".join(str(exc).split())
    return text[:300] + ("..." if len(text) > 300 else "")


def generate(
    contents: Any,
    system: str | None = None,
    json_mode: bool = False,
    temperature: float = 0.7,
    retries: int = 1,
) -> str:
    """Send a request to Gemini and return plain text.

    The primary model is retried on transient errors, then fallback models are
    tried once each. This handles temporary 503 high-demand spikes and retired
    model names. Authentication failures stop immediately.
    """
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        response_mime_type="application/json" if json_mode else None,
    )
    client = _get_client()
    models = get_model_candidates()
    errors: list[tuple[str, Exception]] = []
    last_code: int | None = None

    for index, model in enumerate(models):
        attempts = retries + 1 if index == 0 else 1
        for attempt in range(attempts):
            try:
                response = client.models.generate_content(
                    model=model, contents=contents, config=config
                )
                return response.text or ""
            except Exception as exc:  # noqa: BLE001 - the UI needs a friendly error
                code = _status_code(exc)
                last_code = code
                errors.append((model, exc))
                if code in {400, 401, 403}:
                    raise LLMError(
                        f"Gemini rejected the request ({code}). Check GEMINI_API_KEY and "
                        f"the model name in .env. Details: {_error_summary(exc)}"
                    ) from exc
                if attempt < attempts - 1 and (code is None or code in RETRYABLE_CODES):
                    time.sleep(1.5 * (attempt + 1))

    tried = ", ".join(dict.fromkeys(model for model, _ in errors))
    detail = _error_summary(errors[-1][1]) if errors else "no response"
    if last_code == 503:
        hint = (
            " The model is temporarily overloaded. Wait a minute, or set "
            "GEMINI_MODEL=gemini-3.5-flash-lite in .env."
        )
    elif last_code == 429:
        hint = " The free-tier quota is exhausted. Wait and try again, or use another model."
    elif last_code == 404:
        hint = (
            " One or more models are unavailable. Run the app with a supported model, "
            "or override GEMINI_FALLBACK_MODELS in .env."
        )
    else:
        hint = " Try again, or set GEMINI_MODEL to another Gemini model in .env."
    cause = errors[-1][1] if errors else None
    raise LLMError(
        f"Gemini is unavailable after trying: {tried}.{hint} Details: {detail}"
    ) from cause
