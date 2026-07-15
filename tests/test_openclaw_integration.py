from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from brainwatch.integrations.openclaw import (
    IntegrationError,
    apply_chain,
    model_reference,
    rollback,
    status,
)


def chain() -> list[dict[str, object]]:
    return [
        {"provider": "openrouter", "model_id": "vendor/primary:free"},
        {"provider": "friend", "model_id": "fallback"},
    ]


def config(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "agents": {
                    "defaults": {
                        "model": {
                            "primary": "openrouter/old/primary:free",
                            "fallbacks": ["openrouter/old/fallback:free"],
                        },
                        "unrelated": True,
                    }
                },
                "other": {"kept": 42},
            }
        )
    )
    return path


def test_model_reference_is_deterministic() -> None:
    assert model_reference(chain()[0]) == "openrouter/vendor/primary:free"
    assert model_reference({"provider": "friend", "model_id": "friend/already"}) == (
        "friend/already"
    )


def test_apply_requires_confirmation_before_file_access(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(IntegrationError, match="--yes"):
        apply_chain(chain(), config_path=missing, backup_dir=tmp_path / "backups", confirmed=False)


def test_apply_rejects_empty_chain_and_unknown_shape(tmp_path: Path) -> None:
    source = config(tmp_path / "openclaw.json")
    with pytest.raises(IntegrationError, match="empty"):
        apply_chain([], config_path=source, backup_dir=tmp_path / "backups", confirmed=True)

    source.write_text(json.dumps({"default_model": "old"}))
    with pytest.raises(IntegrationError, match="agents.defaults.model"):
        apply_chain(chain(), config_path=source, backup_dir=tmp_path / "backups", confirmed=True)


def test_backup_apply_and_rollback_cycle(tmp_path: Path) -> None:
    source = config(tmp_path / "openclaw.json")
    result = apply_chain(
        chain(), config_path=source, backup_dir=tmp_path / "backups", confirmed=True
    )
    backup = Path(result["backup"])
    assert backup.is_file()
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600

    updated = json.loads(source.read_text())
    model = updated["agents"]["defaults"]["model"]
    assert model["primary"] == "openrouter/vendor/primary:free"
    assert model["fallbacks"] == ["friend/fallback"]
    assert updated["other"] == {"kept": 42}

    restored = rollback(backup, config_path=source)
    assert restored["restored"] == str(source)
    original = json.loads(source.read_text())
    assert original["agents"]["defaults"]["model"]["primary"] == (
        "openrouter/old/primary:free"
    )


def test_rollback_refuses_invalid_backup(tmp_path: Path) -> None:
    source = config(tmp_path / "openclaw.json")
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    with pytest.raises(IntegrationError, match="invalid backup"):
        rollback(bad, config_path=source)


def test_status_compares_current_chain_with_latest_evidence(tmp_path: Path) -> None:
    source = config(tmp_path / "openclaw.json")
    latest = tmp_path / "latest.json"
    latest.write_text(
        json.dumps(
            {
                "generated_at": 1,
                "all_results": [
                    {
                        "provider": "openrouter",
                        "model_id": "old/primary:free",
                        "model_key": "openrouter:old/primary:free",
                        "status": "ok",
                    },
                    {
                        "provider": "openrouter",
                        "model_id": "old/fallback:free",
                        "model_key": "openrouter:old/fallback:free",
                        "status": "server_error",
                    },
                ],
            }
        )
    )
    result = status(config_path=source, latest_path=latest)
    assert result["all_passing"] is False
    assert result["down_models"] == ["openrouter/old/fallback:free"]
    assert result["evidence_generated_at"] == 1
