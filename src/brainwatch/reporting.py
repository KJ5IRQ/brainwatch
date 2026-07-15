"""Machine-readable and human-readable Brainwatch reports."""

from __future__ import annotations

import json
import time
from typing import Any

from .models import ModelCandidate, ProbeRecord
from .ranking import ScoredCandidate
from .security import redact_text
from .storage import StoragePaths, atomic_write_text


def _reason(
    candidate: ModelCandidate,
    probe: ProbeRecord,
    history: dict[str, object] | None,
) -> str:
    parts = [
        "verified_zero_cost",
        f"context={candidate.context_length}",
        f"status={probe.status}",
    ]
    if probe.latency_ms is not None:
        parts.append(f"latency={probe.latency_ms}ms")
    if candidate.tags:
        parts.append(f"tags={','.join(candidate.tags)}")
    if history and int(history.get("probes", 0)) >= 2:
        parts.append(
            f"history_fail_rate={float(history.get('fail_rate', 0)) * 100:.0f}%"
        )
    return "; ".join(parts)


def build_chain(
    scored: list[ScoredCandidate],
    top: int = 3,
    stability: dict[str, dict[str, object]] | None = None,
) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    for value, candidate, probe in scored:
        if probe.status != "ok":
            continue
        history = (stability or {}).get(candidate.key)
        if (
            history
            and int(history.get("probes", 0)) >= 2
            and float(history.get("fail_rate", 0)) >= 1.0
        ):
            continue
        entry: dict[str, Any] = {
            "rank": len(chain) + 1,
            "provider": candidate.provider,
            "model_id": candidate.model_id,
            "model_key": candidate.key,
            "score": value,
            "latency_ms": probe.latency_ms,
            "context_length": candidate.context_length,
            "tags": list(candidate.tags),
            "reason": _reason(candidate, probe, history),
        }
        if history:
            entry["stability"] = history
        chain.append(entry)
        if len(chain) >= top:
            break
    return chain


def _provider_summary(
    candidates: list[ModelCandidate],
    results: list[ProbeRecord],
    errors: dict[str, str],
) -> dict[str, dict[str, object]]:
    names = {candidate.provider for candidate in candidates} | set(errors)
    output: dict[str, dict[str, object]] = {}
    for name in sorted(names):
        provider_candidates = [item for item in candidates if item.provider == name]
        provider_results = [item for item in results if item.provider == name]
        output[name] = {
            "candidates": len(provider_candidates),
            "probed": sum(item.attempts > 0 for item in provider_results),
            "passed": sum(item.status == "ok" for item in provider_results),
            "refused": sum(item.status.startswith("refused_") for item in provider_results),
            "error": redact_text(errors[name]) if name in errors else None,
        }
    return output


def _status_text(report: dict[str, Any]) -> str:
    lines = [
        "BRAINWATCH MODEL AVAILABILITY REPORT",
        f"generated_at: {report['generated_at_iso']}",
        "policy: verified-zero-cost policy; unknown-cost models are not probed",
        "",
        f"candidates: {report['candidate_count']}",
        f"probed: {report['probed']}",
        f"passed: {report['passed']}",
        f"failed_or_refused: {report['failed_or_refused']}",
        "",
    ]
    if report["proposed_chain"]:
        lines.append("PROPOSED VERIFIED-FREE CHAIN")
        for item in report["proposed_chain"]:
            lines.append(
                f"  {item['rank']}. {item['model_key']} score={item['score']} "
                f"latency={item['latency_ms']}ms"
            )
            lines.append(f"     {item['reason']}")
    else:
        lines.append("No verified-free model passed. Paid and unknown-cost models were not used.")
    lines.extend(("", "RESULTS"))
    for item in report["all_results"]:
        error = f" error={item['error']}" if item["error"] else ""
        lines.append(
            f"  {item['status']:<24} {item['model_key']} latency={item['latency_ms']}{error}"
        )
    return "\n".join(lines) + "\n"


def write_reports(
    paths: StoragePaths,
    *,
    candidates: list[ModelCandidate],
    results: list[ProbeRecord],
    provider_errors: dict[str, str],
    chain: list[dict[str, Any]],
    stability: dict[str, dict[str, object]],
) -> dict[str, Any]:
    timestamp = round(time.time(), 3)
    by_key = {candidate.key: candidate for candidate in candidates}
    all_results: list[dict[str, Any]] = []
    for result in results:
        candidate = by_key.get(result.key)
        row = result.to_dict()
        row["tags"] = list(candidate.tags) if candidate else []
        row["context_length"] = candidate.context_length if candidate else 0
        row["stability"] = stability.get(result.key)
        row["error"] = redact_text(result.error) if result.error else None
        all_results.append(row)
    all_results.sort(key=lambda row: (str(row["provider"]), str(row["model_id"])))

    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": timestamp,
        "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp)),
        "generator": "brainwatch",
        "spend_policy": "verified_zero_only",
        "estimated_paid_spend_usd": 0.0,
        "candidate_count": len(candidates),
        "probed": sum(result.attempts > 0 for result in results),
        "passed": sum(result.status == "ok" for result in results),
        "failed_or_refused": sum(result.status != "ok" for result in results),
        "providers": _provider_summary(candidates, results, provider_errors),
        "proposed_chain": chain,
        "all_results": all_results,
    }
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    atomic_write_text(paths.latest_report, payload, mode=0o600)
    atomic_write_text(paths.proposed_chain, json.dumps(chain, indent=2) + "\n", mode=0o600)
    atomic_write_text(paths.status_report, _status_text(report), mode=0o600)
    return report
