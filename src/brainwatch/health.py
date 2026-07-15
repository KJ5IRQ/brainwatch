"""Provider-isolated Brainwatch health orchestration."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Any

from .config import ConfigError, ProviderConfig, Settings
from .ledger import record_availability, record_probe, rotate
from .models import ModelCandidate, ProbeRecord
from .providers import OpenAICompatibleProvider, OpenRouterProvider, Provider
from .providers.probe import probe_candidate
from .ranking import rank_candidates
from .reporting import build_chain, write_reports
from .security import redact_text
from .storage import StoragePaths
from .trend import load_usage, stability

ProviderFactory = Callable[[ProviderConfig, Settings], Provider]


@dataclass(frozen=True, slots=True)
class HealthOutcome:
    exit_code: int
    report: dict[str, Any]
    paths: StoragePaths


def create_provider(config: ProviderConfig, settings: Settings) -> Provider:
    if config.kind == "openrouter":
        return OpenRouterProvider(
            config, request_timeout_seconds=settings.request_timeout_seconds
        )
    return OpenAICompatibleProvider(
        config, request_timeout_seconds=settings.request_timeout_seconds
    )


def _failure(candidate: ModelCandidate, status: str, error: object) -> ProbeRecord:
    return ProbeRecord(
        provider=candidate.provider,
        model_id=candidate.model_id,
        timestamp=round(time.time(), 3),
        status=status,
        latency_ms=None,
        parsed_ok=False,
        mode=None,
        attempts=0,
        recovered=False,
        http_status=None,
        error=redact_text(error),
    )


def _selected_configs(
    settings: Settings, provider_names: Sequence[str] | None
) -> tuple[ProviderConfig, ...]:
    if not provider_names:
        return settings.providers
    requested = set(provider_names)
    by_name = {provider.name: provider for provider in settings.providers}
    missing = sorted(requested - set(by_name))
    if missing:
        raise ConfigError(f"unknown provider: {', '.join(missing)}")
    return tuple(by_name[name] for name in provider_names)


def run_health(
    settings: Settings,
    *,
    provider_names: Sequence[str] | None = None,
    top: int = 3,
    retain: int | None = None,
    provider_factory: ProviderFactory = create_provider,
) -> HealthOutcome:
    """Discover and probe providers independently, then persist one evidence report."""
    if top < 1:
        raise ConfigError("top must be at least 1")
    configs = _selected_configs(settings, provider_names)
    paths = StoragePaths.from_root(settings.data_dir)
    paths.ensure_writable_dirs()

    providers: dict[str, Provider] = {}
    candidates: list[ModelCandidate] = []
    provider_errors: dict[str, str] = {}
    for config in configs:
        try:
            provider = provider_factory(config, settings)
            providers[config.name] = provider
            candidates.extend(provider.discover_models())
        except Exception as exc:  # provider boundary: one failure must not stop the rest
            provider_errors[config.name] = redact_text(exc)

    record_availability(paths, candidates, provider_errors)

    futures: dict[Future[ProbeRecord], ModelCandidate] = {}
    executor = ThreadPoolExecutor(max_workers=settings.max_workers)
    try:
        for candidate in candidates:
            provider = providers[candidate.provider]
            future = executor.submit(probe_candidate, provider, candidate)
            futures[future] = candidate
        done, pending = wait(futures, timeout=settings.overall_timeout_seconds)
        results: list[ProbeRecord] = []
        for future in done:
            candidate = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append(_failure(candidate, "probe_error", exc))
        for future in pending:
            candidate = futures[future]
            future.cancel()
            results.append(
                _failure(candidate, "overall_timeout", "overall health deadline exceeded")
            )
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    results.sort(key=lambda result: result.key)
    for result in results:
        record_probe(paths, result)
    rotate(paths.usage_ledger, retain)
    rotate(paths.availability_ledger, retain)

    history = stability(load_usage(paths.usage_ledger))
    scored = rank_candidates(candidates, results, history)
    chain = build_chain(scored, top=top, stability=history)
    report = write_reports(
        paths,
        candidates=candidates,
        results=results,
        provider_errors=provider_errors,
        chain=chain,
        stability=history,
    )
    return HealthOutcome(exit_code=0 if chain else 2, report=report, paths=paths)
