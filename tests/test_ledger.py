from __future__ import annotations

import json
from pathlib import Path

from brainwatch.ledger import append_record, record_probe, rotate
from brainwatch.models import ProbeRecord
from brainwatch.storage import StoragePaths


def test_append_strips_secret_shaped_fields_recursively(tmp_path: Path) -> None:
    target = tmp_path / "ledger.jsonl"
    append_record(
        target,
        {
            "model": "safe",
            "Authorization": "Bearer hidden",
            "nested": {"api_key": "hidden", "status": "ok"},
            "headers": {"x": "hidden"},
        },
    )
    saved = json.loads(target.read_text())
    assert saved == {"model": "safe", "nested": {"status": "ok"}}


def test_probe_record_and_retention_keep_newest(tmp_path: Path) -> None:
    paths = StoragePaths.from_root(tmp_path / "state")
    paths.ensure_writable_dirs()
    for index in range(5):
        record_probe(
            paths,
            ProbeRecord(
                provider="friend",
                model_id="same",
                timestamp=float(index),
                status="ok",
                latency_ms=float(index),
                parsed_ok=True,
                mode="content",
                attempts=1,
                recovered=False,
                http_status=200,
            ),
        )
    assert rotate(paths.usage_ledger, 2) == (5, 2)
    rows = [json.loads(line) for line in paths.usage_ledger.read_text().splitlines()]
    assert [row["timestamp"] for row in rows] == [3.0, 4.0]
