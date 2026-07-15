"""Explicit, reversible OpenClaw model-chain integration."""

from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from brainwatch.storage import atomic_write_text, write_protected_text


class IntegrationError(RuntimeError):
    """Raised when an integration action would be ambiguous or unsafe."""


def model_reference(entry: dict[str, object]) -> str:
    provider = entry.get("provider")
    model_id = entry.get("model_id")
    if not isinstance(provider, str) or not provider:
        raise IntegrationError("chain entry requires a provider")
    if not isinstance(model_id, str) or not model_id:
        raise IntegrationError("chain entry requires a model_id")
    if model_id.startswith(f"{provider}/"):
        return model_id
    return f"{provider}/{model_id}"


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise IntegrationError(f"{label} not found: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise IntegrationError(f"invalid {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise IntegrationError(f"{label} must contain a JSON object")
    return value


def _model_block(document: dict[str, Any]) -> dict[str, Any]:
    agents = document.get("agents")
    defaults = agents.get("defaults") if isinstance(agents, dict) else None
    model = defaults.get("model") if isinstance(defaults, dict) else None
    if not isinstance(model, dict):
        raise IntegrationError("OpenClaw config requires agents.defaults.model")
    primary = model.get("primary")
    fallbacks = model.get("fallbacks")
    if not isinstance(primary, str) or not isinstance(fallbacks, list) or not all(
        isinstance(item, str) for item in fallbacks
    ):
        raise IntegrationError(
            "OpenClaw agents.defaults.model requires string primary and list fallbacks"
        )
    return model


def _backup(source: Path, backup_dir: Path) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    destination = backup_dir / f"openclaw-{stamp}-{time.time_ns()}.json.bak"
    write_protected_text(destination, source.read_text(encoding="utf-8"))
    return destination


def apply_chain(
    chain: list[dict[str, object]],
    *,
    config_path: str | Path,
    backup_dir: str | Path,
    confirmed: bool,
) -> dict[str, object]:
    if not confirmed:
        raise IntegrationError("refusing OpenClaw write without --yes")
    if not chain:
        raise IntegrationError("refusing to apply an empty chain")
    source = Path(config_path).expanduser()
    document = _read_json(source, label="OpenClaw config")
    _model_block(document)
    references = [model_reference(entry) for entry in chain]

    updated = deepcopy(document)
    updated_model = _model_block(updated)
    updated_model["primary"] = references[0]
    updated_model["fallbacks"] = references[1:5]
    encoded = json.dumps(updated, indent=2, sort_keys=True) + "\n"
    try:
        validated = json.loads(encoded)
    except json.JSONDecodeError as exc:  # defensive; json.dumps should make this impossible
        raise IntegrationError(f"refusing invalid generated configuration: {exc}") from exc
    _model_block(validated)

    backup = _backup(source, Path(backup_dir).expanduser())
    atomic_write_text(source, encoded, mode=0o600)
    return {
        "backup": str(backup),
        "config": str(source),
        "primary": references[0],
        "fallbacks": references[1:5],
        "validated": True,
    }


def rollback(backup_path: str | Path, *, config_path: str | Path) -> dict[str, str]:
    backup = Path(backup_path).expanduser()
    destination = Path(config_path).expanduser()
    try:
        document = _read_json(backup, label="backup")
        _model_block(document)
    except IntegrationError as exc:
        raise IntegrationError(f"invalid backup; refusing rollback: {exc}") from exc
    atomic_write_text(
        destination,
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        mode=0o600,
    )
    return {"restored": str(destination), "from_backup": str(backup)}


def _reference_key(reference: str) -> str:
    if "/" not in reference:
        return reference
    provider, model_id = reference.split("/", 1)
    return f"{provider}:{model_id}"


def status(*, config_path: str | Path, latest_path: str | Path) -> dict[str, object]:
    document = _read_json(Path(config_path).expanduser(), label="OpenClaw config")
    model = _model_block(document)
    latest = _read_json(Path(latest_path).expanduser(), label="Brainwatch evidence")
    results = latest.get("all_results")
    if not isinstance(results, list):
        raise IntegrationError("Brainwatch evidence requires all_results")
    by_key = {
        row.get("model_key"): row
        for row in results
        if isinstance(row, dict) and isinstance(row.get("model_key"), str)
    }

    references = [model["primary"], *model["fallbacks"]]
    current: list[dict[str, object]] = []
    down: list[str] = []
    for reference in references:
        key = _reference_key(reference)
        evidence = by_key.get(key)
        present = isinstance(evidence, dict)
        state = evidence.get("status") if present else "missing_in_latest"
        healthy = present and state == "ok"
        if not healthy:
            down.append(reference)
        current.append(
            {
                "reference": reference,
                "model_key": key,
                "present_in_latest": present,
                "status": state,
                "healthy": healthy,
            }
        )
    return {
        "current": current,
        "all_passing": not down,
        "down_models": down,
        "evidence_generated_at": latest.get("generated_at"),
    }
