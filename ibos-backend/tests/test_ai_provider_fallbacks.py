from dataclasses import dataclass

import pytest

from app.core.config import settings
from app.services import ai_service
from app.services.ai_service import (
    AIProviderExecution,
    AIProviderResult,
    _complete_with_provider_fallback,
    _resolve_provider_model,
    _resolve_provider_order,
)


@dataclass
class _FakeProvider:
    provider: str
    model: str
    response_text: str | None = None
    error: str | None = None

    def complete(self, *, system_prompt: str, user_prompt: str) -> AIProviderResult:
        if self.error:
            raise RuntimeError(self.error)
        return AIProviderResult(
            text=self.response_text or "",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            estimated_cost_usd=0.0015,
        )


def test_complete_with_provider_fallback_uses_next_provider_after_failure(monkeypatch):
    providers = [
        _FakeProvider(provider="deepseek", model="deepseek-chat", error="timeout"),
        _FakeProvider(provider="openai", model="gpt-4o-mini", response_text="fallback answer"),
    ]
    monkeypatch.setattr(ai_service, "_build_provider_chain", lambda: (providers, []))

    result = _complete_with_provider_fallback(system_prompt="system", user_prompt="user")

    assert isinstance(result, AIProviderExecution)
    assert result.provider == "openai"
    assert result.model == "gpt-4o-mini"
    assert result.completion.text == "fallback answer"
    assert result.attempts == [
        {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "status": "failed",
            "error": "timeout",
        },
        {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "status": "success",
            "error": None,
        },
    ]


def test_complete_with_provider_fallback_raises_clear_error_when_no_provider_is_usable(monkeypatch):
    monkeypatch.setattr(
        ai_service,
        "_build_provider_chain",
        lambda: (
            [],
            [
                {
                    "provider": "deepseek",
                    "model": "deepseek-chat",
                    "status": "skipped",
                    "error": "DEEPSEEK_API_KEY is not configured",
                },
                {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "status": "skipped",
                    "error": "OPENAI_API_KEY is not configured",
                },
            ],
        ),
    )

    with pytest.raises(ValueError, match="No usable AI provider is configured"):
        _complete_with_provider_fallback(system_prompt="system", user_prompt="user")


def test_resolve_provider_order_defaults_to_deepseek_then_openai_then_groq():
    original_provider = settings.ai_provider
    original_fallbacks = list(settings.ai_fallback_providers)
    original_stub_fallback = settings.ai_stub_fallback_enabled
    try:
        settings.ai_provider = "deepseek"
        settings.ai_fallback_providers = []
        settings.ai_stub_fallback_enabled = True
        assert _resolve_provider_order() == ["deepseek", "openai", "groq", "stub"]
    finally:
        settings.ai_provider = original_provider
        settings.ai_fallback_providers = original_fallbacks
        settings.ai_stub_fallback_enabled = original_stub_fallback


def test_resolve_provider_order_defaults_to_stub_only_for_deterministic_mode():
    original_provider = settings.ai_provider
    original_fallbacks = list(settings.ai_fallback_providers)
    original_stub_fallback = settings.ai_stub_fallback_enabled
    try:
        settings.ai_provider = "stub"
        settings.ai_fallback_providers = []
        settings.ai_stub_fallback_enabled = True
        assert _resolve_provider_order() == ["stub"]
    finally:
        settings.ai_provider = original_provider
        settings.ai_fallback_providers = original_fallbacks
        settings.ai_stub_fallback_enabled = original_stub_fallback


def test_resolve_provider_model_uses_provider_specific_defaults_when_shared_model_is_stub_default():
    original_ai_model = settings.ai_model
    original_deepseek_model = settings.deepseek_model
    original_openai_model = settings.openai_model
    original_groq_model = settings.groq_model
    try:
        settings.ai_model = "monidesk-rule-v1"
        settings.deepseek_model = None
        settings.openai_model = None
        settings.groq_model = None

        assert _resolve_provider_model("deepseek") == "deepseek-chat"
        assert _resolve_provider_model("openai") == "gpt-4o-mini"
        assert _resolve_provider_model("groq") == "llama-3.3-70b-versatile"
    finally:
        settings.ai_model = original_ai_model
        settings.deepseek_model = original_deepseek_model
        settings.openai_model = original_openai_model
        settings.groq_model = original_groq_model
