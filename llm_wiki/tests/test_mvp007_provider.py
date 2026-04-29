from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_wiki.app import build_provider, provider_ping
from llm_wiki.core.config import AppConfig
from llm_wiki.llm.groq_provider import GroqProvider


def test_build_provider_uses_config_model_and_key() -> None:
    cfg = AppConfig(
        provider="groq",
        model="llama-3.3-70b-versatile",
        groq_api_key="secret",
    )
    provider = build_provider(cfg)
    assert provider.provider_name() == "groq"
    assert provider.config.model == "llama-3.3-70b-versatile"
    assert provider.config.api_key == "secret"


def test_build_provider_rejects_unknown_provider() -> None:
    cfg = AppConfig(provider="openai", model="gpt-4.1")
    with pytest.raises(ValueError):
        build_provider(cfg)


def test_validate_configuration_requires_key() -> None:
    provider = GroqProvider.from_values(api_key="", model="llama-x")
    with pytest.raises(ValueError):
        provider.validate_configuration()


def test_generate_text_parses_groq_response(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = GroqProvider.from_values(api_key="k", model="llama-x")

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "generated output",
                            }
                        }
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(_request, timeout=60):
        assert timeout == 60
        return _FakeResponse()

    monkeypatch.setattr("llm_wiki.llm.groq_provider.request.urlopen", fake_urlopen)
    out = provider.generate_text("sys", "user")
    assert out == "generated output"


def test_generate_with_image_requires_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    provider = GroqProvider.from_values(api_key="k", model="llama-x")
    image = tmp_path / "a.png"
    image.write_bytes(b"fakeimg")

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return b'{"choices":[{"message":{"content":"ok"}}]}'

    monkeypatch.setattr("llm_wiki.llm.groq_provider.request.urlopen", lambda *_args, **_kwargs: _FakeResponse())
    out = provider.generate_with_image("sys", "user", str(image))
    assert out == "ok"


def test_provider_ping_success(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = GroqProvider.from_values(api_key="k", model="llama-x")
    monkeypatch.setattr(provider, "generate_text", lambda *args, **kwargs: "pong")
    ok, latency_ms, detail = provider_ping(provider)
    assert ok is True
    assert latency_ms >= 0.0
    assert detail == "ok"
