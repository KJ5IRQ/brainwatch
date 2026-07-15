from __future__ import annotations

import json
import stat
from pathlib import Path

from brainwatch.models import ModelCandidate, ProbeRecord
from brainwatch.storage import StoragePaths, atomic_write_text, write_protected_text


def test_storage_paths_do_not_create_directories_until_requested(tmp_path: Path) -> None:
    root = tmp_path / "state"
    paths = StoragePaths.from_root(root)
    assert paths.latest_report == root / "reports" / "latest.json"
    assert not root.exists()
    paths.ensure_writable_dirs()
    assert paths.ledger_dir.is_dir()
    assert paths.reports_dir.is_dir()
    assert paths.backups_dir.is_dir()


def test_atomic_and_protected_writes(tmp_path: Path) -> None:
    normal = tmp_path / "nested" / "record.json"
    atomic_write_text(normal, '{"ok": true}\n')
    assert json.loads(normal.read_text()) == {"ok": True}

    protected = tmp_path / "secret-adjacent.txt"
    write_protected_text(protected, "safe\n")
    assert protected.read_text() == "safe\n"
    assert stat.S_IMODE(protected.stat().st_mode) == 0o600


def test_normalized_records_are_secret_free_and_serializable() -> None:
    candidate = ModelCandidate(
        provider="lab",
        model_id="coder",
        display_name="Coder",
        context_length=8192,
        tags=("coding",),
        cost_verified=True,
        prompt_price="0",
        completion_price="0",
    )
    assert candidate.key == "lab:coder"
    assert candidate.to_dict()["tags"] == ["coding"]

    record = ProbeRecord(
        provider="lab",
        model_id="coder",
        timestamp=1.5,
        status="ok",
        latency_ms=12.0,
        parsed_ok=True,
        mode="content",
        attempts=1,
        recovered=False,
        http_status=200,
        error=None,
        prompt_tokens=4,
        completion_tokens=2,
    )
    serialized = record.to_dict()
    assert serialized["model_key"] == "lab:coder"
    assert "headers" not in serialized
    assert "Authorization" not in serialized
    json.dumps(serialized)
