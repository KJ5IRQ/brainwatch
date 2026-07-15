from __future__ import annotations

from unittest import mock

from brainwatch.config import ProviderConfig
from brainwatch.providers.openrouter import OpenRouterProvider


def provider_config() -> ProviderConfig:
    return ProviderConfig(
        name="openrouter",
        kind="openrouter",
        base_url="https://openrouter.ai/api",
        api_key_env="OPENROUTER_API_KEY",
        models_path="/v1/models",
        chat_path="/v1/chat/completions",
        free_models=(),
    )


def response(payload: object, status: int = 200) -> mock.Mock:
    item = mock.Mock()
    item.status_code = status
    item.json.return_value = payload
    return item


def test_openrouter_discovers_only_verified_free_text_models() -> None:
    session = mock.Mock()
    session.get.return_value = response(
        {
            "data": [
                {
                    "id": "free/text:free",
                    "name": "Free Text",
                    "context_length": 32768,
                    "pricing": {"prompt": "0", "completion": "0"},
                    "architecture": {"output_modalities": ["text"]},
                },
                {
                    "id": "paid/text",
                    "pricing": {"prompt": "0.1", "completion": "0"},
                    "architecture": {"output_modalities": ["text"]},
                },
                {
                    "id": "broken/price",
                    "pricing": {"prompt": "free", "completion": "0"},
                    "architecture": {"output_modalities": ["text"]},
                },
                {
                    "id": "free/audio",
                    "pricing": {"prompt": "0", "completion": "0"},
                    "architecture": {"output_modalities": ["text", "audio"]},
                },
            ]
        }
    )
    provider = OpenRouterProvider(
        provider_config(), session=session, environ={"OPENROUTER_API_KEY": "secret"}
    )
    candidates = provider.discover_models()
    assert [candidate.model_id for candidate in candidates] == ["free/text:free"]
    assert candidates[0].cost_verified is True
    assert candidates[0].provider == "openrouter"
    assert session.get.call_args.args[0] == "https://openrouter.ai/api/v1/models"


def test_openrouter_probe_uses_catalog_model_and_bearer_secret() -> None:
    session = mock.Mock()
    session.post.return_value = response(
        {
            "choices": [{"message": {"content": '{"ok": true, "n": 42}'}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 4},
        }
    )
    provider = OpenRouterProvider(
        provider_config(), session=session, environ={"OPENROUTER_API_KEY": "secret"}
    )
    candidate = mock.Mock(provider="openrouter", model_id="free/text:free")
    record = provider.probe(candidate)
    assert record.status == "ok"
    _, kwargs = session.post.call_args
    assert kwargs["json"]["model"] == "free/text:free"
    assert kwargs["headers"]["Authorization"] == "Bearer secret"
