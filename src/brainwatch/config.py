"""Configuration loading and validation for Brainwatch."""

from __future__ import annotations

import ipaddress
import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit


class ConfigError(ValueError):
    """Raised when Brainwatch configuration is missing or unsafe."""


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    name: str
    kind: Literal["openrouter", "openai-compatible"]
    base_url: str
    api_key_env: str
    models_path: str
    chat_path: str
    free_models: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Settings:
    config_path: Path
    data_dir: Path
    providers: tuple[ProviderConfig, ...]
    request_timeout_seconds: float
    overall_timeout_seconds: float
    max_workers: int


def _home(environ: Mapping[str, str]) -> Path:
    return Path(environ.get("HOME", str(Path.home()))).expanduser()


def default_config_path(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    root = Path(env.get("XDG_CONFIG_HOME", _home(env) / ".config"))
    return root / "brainwatch" / "config.toml"


def default_data_dir(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    root = Path(env.get("XDG_DATA_HOME", _home(env) / ".local" / "share"))
    return root / "brainwatch"


def _is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_base_url(value: str) -> str:
    """Require HTTPS for remote providers and reject embedded credentials."""
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc or parsed.hostname is None:
        raise ConfigError("base_url must be an absolute URL")
    if parsed.username is not None or parsed.password is not None:
        raise ConfigError("base_url must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ConfigError("base_url must not contain a query or fragment")
    if parsed.scheme == "http" and not _is_loopback(parsed.hostname):
        raise ConfigError("remote base_url must use HTTPS")
    if parsed.scheme not in {"http", "https"}:
        raise ConfigError("base_url scheme must be HTTP or HTTPS")
    return value.rstrip("/")


def _positive_number(value: object, name: str, default: float) -> float:
    raw = default if value is None else value
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw <= 0:
        raise ConfigError(f"{name} must be a positive number")
    return float(raw)


def _provider(raw: object) -> ProviderConfig:
    if not isinstance(raw, dict):
        raise ConfigError("each provider must be a TOML table")
    name = raw.get("name")
    kind = raw.get("kind")
    if not isinstance(name, str) or not name.strip():
        raise ConfigError("provider name must be a non-empty string")
    if kind not in {"openrouter", "openai-compatible"}:
        raise ConfigError(f"provider {name!r} has unsupported kind")

    if kind == "openrouter":
        base_url = validate_base_url(str(raw.get("base_url", "https://openrouter.ai/api")))
        api_key_env = raw.get("api_key_env", "OPENROUTER_API_KEY")
    else:
        if "base_url" not in raw:
            raise ConfigError(f"provider {name!r} requires base_url")
        base_url = validate_base_url(str(raw["base_url"]))
        if "api_key_env" not in raw:
            raise ConfigError(f"provider {name!r} requires api_key_env")
        api_key_env = raw["api_key_env"]

    if not isinstance(api_key_env, str) or not api_key_env.strip():
        raise ConfigError(f"provider {name!r} api_key_env must be a non-empty string")

    free_models_raw = raw.get("free_models", [])
    if not isinstance(free_models_raw, list) or not all(
        isinstance(item, str) and item for item in free_models_raw
    ):
        raise ConfigError(f"provider {name!r} free_models must be a list of model IDs")
    if kind == "openai-compatible" and not free_models_raw:
        raise ConfigError(f"provider {name!r} requires a non-empty free_models list")

    models_path = raw.get("models_path", "/v1/models")
    chat_path = raw.get("chat_path", "/v1/chat/completions")
    if not isinstance(models_path, str) or not models_path.startswith("/"):
        raise ConfigError(f"provider {name!r} models_path must start with /")
    if not isinstance(chat_path, str) or not chat_path.startswith("/"):
        raise ConfigError(f"provider {name!r} chat_path must start with /")

    return ProviderConfig(
        name=name.strip(),
        kind=kind,
        base_url=base_url,
        api_key_env=api_key_env,
        models_path=models_path,
        chat_path=chat_path,
        free_models=tuple(free_models_raw),
    )


def resolve_data_dir(
    data_dir: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Resolve the Brainwatch state directory from args and environment.

    Precedence: explicit *data_dir* argument, ``BRAINWATCH_HOME`` env var,
    XDG default.
    """
    env = os.environ if environ is None else environ
    return Path(data_dir or env.get("BRAINWATCH_HOME", "")).expanduser() or default_data_dir(env)


def load_settings(
    path: str | Path | None = None,
    data_dir: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Settings:
    env = os.environ if environ is None else environ
    selected_path = Path(
        path or env.get("BRAINWATCH_CONFIG", default_config_path(env))
    ).expanduser()
    if not selected_path.is_file():
        raise ConfigError(f"configuration file not found: {selected_path}")
    try:
        with selected_path.open("rb") as handle:
            document = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {selected_path}: {exc}") from exc

    provider_rows = document.get("providers")
    if not isinstance(provider_rows, list) or not provider_rows:
        raise ConfigError("configuration requires at least one [[providers]] table")
    providers = tuple(_provider(row) for row in provider_rows)
    names = [provider.name for provider in providers]
    if len(names) != len(set(names)):
        raise ConfigError("duplicate provider name")

    app = document.get("brainwatch", {})
    if not isinstance(app, dict):
        raise ConfigError("[brainwatch] must be a TOML table")
    workers = app.get("max_workers", 4)
    if isinstance(workers, bool) or not isinstance(workers, int) or not 1 <= workers <= 32:
        raise ConfigError("max_workers must be an integer from 1 through 32")

    selected_data = Path(data_dir or env.get("BRAINWATCH_HOME", default_data_dir(env))).expanduser()
    return Settings(
        config_path=selected_path,
        data_dir=selected_data,
        providers=providers,
        request_timeout_seconds=_positive_number(
            app.get("request_timeout_seconds"), "request_timeout_seconds", 25.0
        ),
        overall_timeout_seconds=_positive_number(
            app.get("overall_timeout_seconds"), "overall_timeout_seconds", 240.0
        ),
        max_workers=workers,
    )
