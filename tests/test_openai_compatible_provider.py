from __future__ import annotations

from unittest import mock

from brainwatch.config import ProviderConfig
from brainwatch.providers.openai_compatible import OpenAICompatibleProvider


def provider_config(base_url: str = "https://models.example.test") -> ProviderConfig:
    return ProviderConfig(
        name="friend",
        kind="openai-compatible",
        base_url=base_url,
        api_key_env="FRIEND_API_KEY",
        models_path="/v1/models",
        chat_path="/v1/chat/completions",
        free_models=("allowed",),
    )


def response(payload: object, status: int = 200) -> mock.Mock:
    item = mock.Mock()
    item.status_code = status
    item.json.return_value = payload
    return item


def test_generic_provider_marks_only_explicit_models_free() -> None:
    session = mock.Mock()
    session.get.return_value = response({"data": [{"id": "allowed"}, {"id": "unknown"}]})
    provider = OpenAICompatibleProvider(
        provider_config(), session=session, environ={"FRIEND_API_KEY": "secret"}
    )
    candidates = provider.discover_models()
    assert [(item.model_id, item.cost_verified) for item in candidates] == [
        ("allowed", True),
        ("unknown", False),
    ]


def test_local_http_provider_still_uses_explicit_allowlist() -> None:
    session = mock.Mock()
    session.get.return_value = response({"data": [{"id": "unknown"}]})
    provider = OpenAICompatibleProvider(
        provider_config("http://127.0.0.1:8000"),
        session=session,
        environ={"FRIEND_API_KEY": "local-placeholder"},
    )
    candidate = provider.discover_models()[0]
    assert candidate.cost_verified is False


def test_endpoint_paths_cannot_replace_provider_origin() -> None:
    bad = ProviderConfig(
        name="friend",
        kind="openai-compatible",
        base_url="https://models.example.test",
        api_key_env="FRIEND_API_KEY",
        models_path="//evil.example/models",
        chat_path="/v1/chat/completions",
        free_models=("allowed",),
    )
    provider = OpenAICompatibleProvider(bad, session=mock.Mock(), environ={})
    with mock.patch("brainwatch.providers.openai_compatible.get_secret", return_value="secret"):
        try:
            provider.discover_models()
        except ValueError as exc:
            assert "endpoint path" in str(exc)
        else:
            raise AssertionError("origin-replacing endpoint was accepted")
