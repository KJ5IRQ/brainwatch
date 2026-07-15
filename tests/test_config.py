from __future__ import annotations

from pathlib import Path

import pytest

from brainwatch.config import ConfigError, load_settings, validate_base_url


def write_config(path: Path, body: str) -> Path:
    path.write_text(body)
    return path


def test_xdg_defaults_and_environment_overrides(tmp_path: Path) -> None:
    config = write_config(
        tmp_path / "brainwatch.toml",
        """
[[providers]]
name = "openrouter"
kind = "openrouter"
""",
    )
    data = tmp_path / "data"
    settings = load_settings(environ={
        "BRAINWATCH_CONFIG": str(config),
        "BRAINWATCH_HOME": str(data),
    })
    assert settings.config_path == config
    assert settings.data_dir == data
    assert not data.exists()


def test_loads_openrouter_and_generic_providers(tmp_path: Path) -> None:
    config = write_config(
        tmp_path / "brainwatch.toml",
        """
[brainwatch]
request_timeout_seconds = 7.5
overall_timeout_seconds = 90
max_workers = 3

[[providers]]
name = "openrouter"
kind = "openrouter"
api_key_env = "OPENROUTER_API_KEY"

[[providers]]
name = "lab"
kind = "openai-compatible"
base_url = "http://127.0.0.1:8000"
api_key_env = "LAB_API_KEY"
free_models = ["small", "coder"]
""",
    )
    settings = load_settings(path=config, data_dir=tmp_path / "state", environ={})
    assert [provider.name for provider in settings.providers] == ["openrouter", "lab"]
    assert settings.providers[0].base_url == "https://openrouter.ai/api"
    assert settings.providers[1].chat_path == "/v1/chat/completions"
    assert settings.providers[1].free_models == ("small", "coder")
    assert settings.request_timeout_seconds == 7.5
    assert settings.overall_timeout_seconds == 90
    assert settings.max_workers == 3


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            """
[[providers]]
name = "same"
kind = "openrouter"
[[providers]]
name = "same"
kind = "openrouter"
""",
            "duplicate provider name",
        ),
        (
            """
[[providers]]
name = "remote"
kind = "openai-compatible"
api_key_env = "REMOTE_KEY"
free_models = ["x"]
""",
            "base_url",
        ),
        (
            """
[[providers]]
name = "remote"
kind = "openai-compatible"
base_url = "https://models.example.test"
free_models = ["x"]
""",
            "api_key_env",
        ),
        (
            """
[[providers]]
name = "remote"
kind = "openai-compatible"
base_url = "https://models.example.test"
api_key_env = "REMOTE_KEY"
free_models = []
""",
            "free_models",
        ),
    ],
)
def test_invalid_provider_config_is_rejected(tmp_path: Path, body: str, message: str) -> None:
    config = write_config(tmp_path / "invalid.toml", body)
    with pytest.raises(ConfigError, match=message):
        load_settings(path=config, environ={})


def test_base_url_transport_policy() -> None:
    assert validate_base_url("https://models.example.test/api") == "https://models.example.test/api"
    assert validate_base_url("http://localhost:8080") == "http://localhost:8080"
    assert validate_base_url("http://127.0.0.1:8080") == "http://127.0.0.1:8080"
    assert validate_base_url("http://[::1]:8080") == "http://[::1]:8080"
    with pytest.raises(ConfigError, match="HTTPS"):
        validate_base_url("http://models.example.test")
    with pytest.raises(ConfigError, match="credentials"):
        validate_base_url("https://user:pass@models.example.test")
