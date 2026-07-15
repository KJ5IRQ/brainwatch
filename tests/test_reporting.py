from __future__ import annotations

import json
from pathlib import Path

from brainwatch.models import ModelCandidate, ProbeRecord
from brainwatch.reporting import build_chain, write_reports
from brainwatch.storage import StoragePaths


def candidate(provider: str, model: str) -> ModelCandidate:
    return ModelCandidate(
        provider=provider,
        model_id=model,
        display_name=model,
        context_length=8192,
        tags=("general",),
        cost_verified=True,
        prompt_price="0",
        completion_price="0",
    )


def record(provider: str, model: str, status: str = "ok") -> ProbeRecord:
    return ProbeRecord(
        provider=provider,
        model_id=model,
        timestamp=1,
        status=status,
        latency_ms=25,
        parsed_ok=status == "ok",
        mode="content",
        attempts=1,
        recovered=False,
        http_status=200,
        error=None if status == "ok" else "synthetic failure",
    )


def test_build_chain_keeps_provider_identity_and_excludes_dead_history() -> None:
    first = candidate("one", "same")
    second = candidate("two", "same")
    scored = [(0.9, first, record("one", "same")), (0.8, second, record("two", "same"))]
    history = {
        "two:same": {
            "model_key": "two:same",
            "probes": 3,
            "passes": 0,
            "fails": 3,
            "fail_rate": 1.0,
            "streak_fails": 3,
        }
    }
    chain = build_chain(scored, top=3, stability=history)
    assert [(item["provider"], item["model_id"]) for item in chain] == [("one", "same")]


def test_reports_are_atomic_neutral_and_include_provider_errors(tmp_path: Path) -> None:
    paths = StoragePaths.from_root(tmp_path / "state")
    paths.ensure_writable_dirs()
    item = candidate("friend", "free-model")
    probe = record("friend", "free-model")
    scored = [(0.9, item, probe)]
    chain = build_chain(scored)
    report = write_reports(
        paths,
        candidates=[item],
        results=[probe],
        provider_errors={"offline": "catalog unavailable"},
        chain=chain,
        stability={},
    )
    on_disk = json.loads(paths.latest_report.read_text())
    assert report == on_disk
    assert on_disk["providers"]["offline"]["error"] == "catalog unavailable"
    assert on_disk["proposed_chain"][0]["model_key"] == "friend:free-model"
    text = paths.status_report.read_text()
    assert text.startswith("BRAINWATCH MODEL AVAILABILITY REPORT")
    assert "verified-zero-cost policy" in text


def test_no_passing_models_explains_refusal(tmp_path: Path) -> None:
    paths = StoragePaths.from_root(tmp_path / "state")
    paths.ensure_writable_dirs()
    item = candidate("friend", "unknown")
    refused = record("friend", "unknown", "refused_unverified_cost")
    write_reports(
        paths,
        candidates=[item],
        results=[refused],
        provider_errors={},
        chain=[],
        stability={},
    )
    assert "No verified-free model passed" in paths.status_report.read_text()
