from __future__ import annotations

import pytest

import escape_room.llm as llm


class FakeResponse:
    text = "the door is locked"


class FakeModels:
    def __init__(self, failures: dict[str, int]):
        self.failures = failures
        self.calls: list[str] = []

    def generate_content(self, model, contents, config):
        self.calls.append(model)
        code = self.failures.get(model)
        if code:
            exc = RuntimeError(f"ServerError: {code} UNAVAILABLE high demand")
            exc.code = code
            raise exc
        return FakeResponse()


class FakeClient:
    def __init__(self, failures: dict[str, int]):
        self.models = FakeModels(failures)


def _install(monkeypatch, failures: dict[str, int], primary: str = "gemini-3.8-flash") -> FakeClient:
    fake = FakeClient(failures)
    monkeypatch.setenv("GEMINI_MODEL", primary)
    monkeypatch.setattr(llm, "_get_client", lambda: fake)
    monkeypatch.setattr(llm.time, "sleep", lambda _: None)
    return fake


def test_falls_back_when_primary_model_is_overloaded(monkeypatch) -> None:
    fake = _install(monkeypatch, {"gemini-3.8-flash": 503})
    assert llm.generate("hello", retries=0) == "the door is locked"
    assert fake.models.calls == ["gemini-3.8-flash", "gemini-3.5-flash-lite"]


def test_auth_error_stops_immediately_without_fallback(monkeypatch) -> None:
    fake = _install(monkeypatch, {"gemini-3.8-flash": 401})
    with pytest.raises(llm.LLMError, match="rejected"):
        llm.generate("hello", retries=0)
    assert fake.models.calls == ["gemini-3.8-flash"]


def test_all_models_failing_reports_503_hint(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    failures = {model: 503 for model in llm.get_model_candidates()}
    _install(monkeypatch, failures)
    with pytest.raises(llm.LLMError) as error:
        llm.generate("hello", retries=0)
    message = str(error.value)
    assert "temporarily overloaded" in message
    assert "GEMINI_MODEL=gemini-3.5-flash-lite" in message
    assert "gemini-3.8-flash" in message


def test_status_code_is_read_from_text_when_missing_attribute() -> None:
    assert llm._status_code(RuntimeError("ServerError: 503 UNAVAILABLE")) == 503
    assert llm._status_code(RuntimeError("no code here")) is None


def test_model_candidates_are_unique(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    monkeypatch.delenv("GEMINI_FALLBACK_MODELS", raising=False)
    candidates = llm.get_model_candidates()
    assert candidates[0] == "gemini-3.8-flash"
    assert len(candidates) == len(set(candidates))
    assert "gemini-3.5-flash-lite" in candidates


def test_fallback_order_can_be_overridden(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "custom-a, custom-b")
    candidates = llm.get_model_candidates()
    assert candidates == ["gemini-3.8-flash", "custom-a", "custom-b"]


def test_missing_key_raises_immediately(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(llm.LLMError, match="GEMINI_API_KEY is not set"):
        llm.generate("hello")
