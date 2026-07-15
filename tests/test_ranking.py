from __future__ import annotations

from brainwatch.models import ModelCandidate, ProbeRecord
from brainwatch.ranking import rank_candidates, score


def candidate(provider: str, model: str) -> ModelCandidate:
    return ModelCandidate(
        provider=provider,
        model_id=model,
        display_name=model,
        context_length=100_000,
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
        latency_ms=100,
        parsed_ok=status == "ok",
        mode="content",
        attempts=1,
        recovered=False,
        http_status=200,
    )


def test_score_is_deterministic_and_failed_probe_loses() -> None:
    item = candidate("one", "a")
    assert score(item, record("one", "a")) == score(item, record("one", "a"))
    assert score(item, record("one", "a")) > score(item, record("one", "a", "timeout"))


def test_historical_failure_penalizes_equal_current_models() -> None:
    candidates = [candidate("one", "a"), candidate("two", "a")]
    results = [record("one", "a"), record("two", "a")]
    history = {
        "two:a": {
            "model_key": "two:a",
            "probes": 4,
            "passes": 1,
            "fails": 3,
            "fail_rate": 0.75,
            "streak_fails": 0,
        }
    }
    ranked = rank_candidates(candidates, results, history)
    assert [item[1].key for item in ranked] == ["one:a", "two:a"]
    assert ranked[0][0] > ranked[1][0]
