"""Historical reliability analysis over probe evidence."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .storage import atomic_write_text


def load_usage(path: str | Path) -> list[dict[str, object]]:
    target = Path(path)
    if not target.exists():
        return []
    records: list[dict[str, object]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def _model_key(record: dict[str, Any]) -> str | None:
    key = record.get("model_key")
    if isinstance(key, str) and key:
        return key
    provider = record.get("provider")
    model_id = record.get("model_id")
    if isinstance(provider, str) and isinstance(model_id, str):
        return f"{provider}:{model_id}"
    return None


def stability(records: list[dict[str, Any]]) -> dict[str, dict[str, object]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = _model_key(record)
        if key is not None:
            grouped[key].append(record)

    output: dict[str, dict[str, object]] = {}
    for key, rows in grouped.items():
        ordered = sorted(rows, key=lambda row: float(row.get("timestamp", 0)))
        statuses = [row.get("status") for row in ordered]
        passes = sum(status == "ok" for status in statuses)
        fails = len(statuses) - passes
        streak = 0
        for status in reversed(statuses):
            if status == "ok":
                break
            streak += 1
        last = ordered[-1]
        output[key] = {
            "model_key": key,
            "probes": len(ordered),
            "passes": passes,
            "fails": fails,
            "fail_rate": fails / len(ordered),
            "streak_fails": streak,
            "last_status": last.get("status"),
            "last_timestamp": last.get("timestamp"),
            "last_latency_ms": last.get("latency_ms"),
        }
    return output


def rank_by_instability(
    stats: dict[str, dict[str, object]], min_probes: int = 1
) -> list[dict[str, object]]:
    items = [item for item in stats.values() if int(item.get("probes", 0)) >= min_probes]
    items.sort(
        key=lambda item: (
            float(item.get("fail_rate", 0)),
            int(item.get("streak_fails", 0)),
            int(item.get("fails", 0)),
        ),
        reverse=True,
    )
    return items


def write_report(
    stats: dict[str, dict[str, object]],
    ranked: list[dict[str, object]],
    *,
    path: str | Path,
) -> str:
    record_count = sum(int(item.get("probes", 0)) for item in stats.values())
    lines = [
        f"probe_records={record_count} models={len(stats)}",
        "worst-first by fail rate and current failure streak",
        "",
        f"{'MODEL':44} {'PASS':>4} {'FAIL':>4} {'RATE':>5} {'STREAK':>7}  LAST",
    ]
    for item in ranked:
        model = str(item.get("model_key", ""))[:44]
        rate = f"{float(item.get('fail_rate', 0)) * 100:.0f}%"
        lines.append(
            f"{model:44} {int(item.get('passes', 0)):>4} "
            f"{int(item.get('fails', 0)):>4} {rate:>5} "
            f"{int(item.get('streak_fails', 0)):>7}  {item.get('last_status', 'unknown')}"
        )
    text = "\n".join(lines) + "\n"
    atomic_write_text(path, text, mode=0o600)
    return text
