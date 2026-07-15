from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest import mock

import pytest

from brainwatch.config import ConfigError, ProviderConfig, Settings
from brainwatch.health import run_health
from brainwatch.models import ModelCandidate, ProbeRecord


def provider_config(name: str) -> ProviderConfig:
    return ProviderConfig(
        name=name,
        kind="openai-compatible",
        base_url="https://models.example.test",
        api_key_env=f"{name.upper()}_KEY",
        models_path="/v1/models",
        chat_path="/v1/chat/completions",
        free_models=("free",),
    )


def settings(tmp_path: Path) -> Settings:
    return Settings(
        config_path=tmp_path / "config.toml",
        data_dir=tmp_path / "state",
        providers=(provider_config("bad"), provider_config("good")),
        request_timeout_seconds=1,
        overall_timeout_seconds=5,
        max_workers=2,
    )


def candidate(name: str, verified: bool = True) -> ModelCandidate:
    return ModelCandidate(
        provider=name,
        model_id="free" if verified else "unknown",
        display_name="Free",
        context_length=8192,
        tags=("general",),
        cost_verified=verified,
        prompt_price="0" if verified else None,
        completion_price="0" if verified else None,
    )


class GoodProvider:
    name = "good"

    def discover_models(self) -> list[ModelCandidate]:
        return [candidate("good")]

    def probe(self, item: ModelCandidate) -> ProbeRecord:
        return ProbeRecord(
            provider=item.provider,
            model_id=item.model_id,
            timestamp=1,
            status="ok",
            latency_ms=10,
            parsed_ok=True,
            mode="content",
            attempts=1,
            recovered=False,
            http_status=200,
        )


class BadProvider:
    name = "bad"

    def discover_models(self) -> list[ModelCandidate]:
        raise RuntimeError("synthetic catalog failure")

    def probe(self, item: ModelCandidate) -> ProbeRecord:
        raise AssertionError("bad provider must not be probed")


class RefusedProvider:
    name = "good"

    def __init__(self) -> None:
        self.probe_calls = 0

    def discover_models(self) -> list[ModelCandidate]:
        return [candidate("good", verified=False)]

    def probe(self, item: ModelCandidate) -> ProbeRecord:
        self.probe_calls += 1
        raise AssertionError("unverified candidate reached provider probe")


def test_provider_failure_isolated_and_worker_count_bounded(tmp_path: Path) -> None:
    providers = {"bad": BadProvider(), "good": GoodProvider()}
    with mock.patch("brainwatch.health.ThreadPoolExecutor", wraps=ThreadPoolExecutor) as pool:
        outcome = run_health(
            settings(tmp_path),
            provider_factory=lambda config, _settings: providers[config.name],
        )
    assert outcome.exit_code == 0
    assert outcome.report["passed"] == 1
    assert outcome.report["providers"]["bad"]["error"] == "synthetic catalog failure"
    assert pool.call_args.kwargs["max_workers"] == 2


def test_provider_selection_and_unknown_name(tmp_path: Path) -> None:
    created: list[str] = []

    def factory(config: ProviderConfig, _settings: Settings):
        created.append(config.name)
        return GoodProvider()

    outcome = run_health(settings(tmp_path), provider_names=("good",), provider_factory=factory)
    assert outcome.exit_code == 0
    assert created == ["good"]
    with pytest.raises(ConfigError, match="unknown provider"):
        run_health(settings(tmp_path), provider_names=("missing",), provider_factory=factory)


def test_all_ineligible_models_exit_two_without_provider_probe(tmp_path: Path) -> None:
    refused = RefusedProvider()
    selected = replace(settings(tmp_path), providers=(provider_config("good"),))
    outcome = run_health(selected, provider_factory=lambda _config, _settings: refused)
    assert outcome.exit_code == 2
    assert outcome.report["passed"] == 0
    assert outcome.report["all_results"][0]["status"] == "refused_unverified_cost"
    assert refused.probe_calls == 0
