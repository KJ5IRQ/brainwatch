from __future__ import annotations

from brainwatch.trend import rank_by_instability, stability


def test_stability_uses_provider_qualified_identity() -> None:
    records = [
        {"provider": "one", "model_id": "same", "timestamp": 1, "status": "ok"},
        {"provider": "two", "model_id": "same", "timestamp": 1, "status": "server_error"},
        {"provider": "two", "model_id": "same", "timestamp": 2, "status": "server_error"},
    ]
    stats = stability(records)
    assert stats["one:same"]["passes"] == 1
    assert stats["two:same"]["fails"] == 2
    assert stats["two:same"]["streak_fails"] == 2


def test_instability_is_worst_first() -> None:
    stats = {
        "stable:model": {
            "model_key": "stable:model",
            "probes": 4,
            "passes": 4,
            "fails": 0,
            "fail_rate": 0.0,
            "streak_fails": 0,
        },
        "bad:model": {
            "model_key": "bad:model",
            "probes": 4,
            "passes": 1,
            "fails": 3,
            "fail_rate": 0.75,
            "streak_fails": 2,
        },
    }
    assert [item["model_key"] for item in rank_by_instability(stats)] == [
        "bad:model",
        "stable:model",
    ]
