"""Secret-safe JSONL evidence ledgers."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from .models import ModelCandidate, ProbeRecord
from .storage import StoragePaths, atomic_write_text

_SECRET_HINTS = ("authorization", "credential", "headers", "password", "secret", "token", "key")


def _secret_key(name: object) -> bool:
    lowered = str(name).lower()
    return any(hint in lowered for hint in _SECRET_HINTS)


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items() if not _secret_key(key)}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize(item) for item in value]
    return value


def append_record(path: str | Path, record: dict[str, object]) -> dict[str, object]:
    """Append one sanitized record using a single O_APPEND write."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    safe = _sanitize(record)
    line = (json.dumps(safe, sort_keys=True, separators=(",", ":")) + "\n").encode()
    descriptor = os.open(target, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(descriptor, line)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return safe


def record_availability(
    paths: StoragePaths,
    candidates: list[ModelCandidate],
    provider_errors: dict[str, str],
) -> dict[str, object]:
    record: dict[str, object] = {
        "timestamp": round(time.time(), 3),
        "candidate_count": len(candidates),
        "candidates": [candidate.key for candidate in candidates],
        "provider_errors": provider_errors,
    }
    return append_record(paths.availability_ledger, record)


def record_probe(paths: StoragePaths, record: ProbeRecord) -> dict[str, object]:
    return append_record(paths.usage_ledger, record.to_dict())


def rotate(path: str | Path, retain: int | None) -> tuple[int, int] | None:
    if retain is None or retain <= 0:
        return None
    target = Path(path)
    if not target.exists():
        return (0, 0)
    lines = [line for line in target.read_text(encoding="utf-8").splitlines() if line]
    before = len(lines)
    if before <= retain:
        return (before, before)
    kept = lines[-retain:]
    atomic_write_text(target, "\n".join(kept) + "\n", mode=0o600)
    return (before, len(kept))
