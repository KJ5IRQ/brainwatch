"""Transparent provider-independent model ranking."""

from __future__ import annotations

import math

from .models import ModelCandidate, ProbeRecord

ScoredCandidate = tuple[float, ModelCandidate, ProbeRecord]


def score(candidate: ModelCandidate, probe: ProbeRecord) -> float:
    context_score = (
        math.log10(candidate.context_length + 1) / math.log10(1_000_001)
        if candidate.context_length
        else 0.0
    )
    latency_score = (
        max(0.0, 1.0 - probe.latency_ms / 3000.0)
        if probe.latency_ms is not None
        else 0.0
    )
    pass_score = 1.0 if probe.status == "ok" else 0.0
    capability_score = 0.0
    if "coding" in candidate.tags:
        capability_score += 0.4
    if "reasoning" in candidate.tags:
        capability_score += 0.3
    if "vision" in candidate.tags:
        capability_score += 0.1
    if "general" in candidate.tags:
        capability_score += 0.2
    mode_score = 0.0 if probe.mode == "reasoning" else 0.05
    total = (
        0.25 * context_score
        + 0.20 * latency_score
        + 0.40 * pass_score
        + 0.10 * min(capability_score, 1.0)
        + mode_score
    )
    return round(total, 4)


def rank_candidates(
    candidates: list[ModelCandidate],
    results: list[ProbeRecord],
    stability: dict[str, dict[str, object]] | None = None,
) -> list[ScoredCandidate]:
    by_key = {result.key: result for result in results}
    scored: list[ScoredCandidate] = []
    for candidate in candidates:
        probe = by_key.get(candidate.key)
        if probe is None:
            continue
        value = score(candidate, probe)
        history = (stability or {}).get(candidate.key)
        if history and int(history.get("probes", 0)) >= 2:
            value = round(value * (1.0 - float(history.get("fail_rate", 0))), 4)
        scored.append((value, candidate, probe))
    scored.sort(key=lambda item: (-item[0], item[1].key))
    return scored
