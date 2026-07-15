from __future__ import annotations

import json
from pathlib import Path

from brainwatch.config import load_settings

ROOT = Path(__file__).resolve().parents[1]


def test_example_config_loads_without_accessing_credentials(tmp_path: Path) -> None:
    settings = load_settings(
        path=ROOT / "config.example.toml",
        data_dir=tmp_path / "state",
        environ={},
    )
    assert [provider.kind for provider in settings.providers] == [
        "openrouter",
        "openai-compatible",
        "openai-compatible",
    ]
    assert settings.providers[2].free_models == ("example-free-model",)


def test_synthetic_examples_are_valid_json() -> None:
    for path in (ROOT / "examples").glob("*.json"):
        json.loads(path.read_text())
    for path in (ROOT / "examples").glob("*.jsonl"):
        for line in path.read_text().splitlines():
            json.loads(line)


def test_systemd_units_are_user_level_and_bounded() -> None:
    service = (ROOT / "deploy" / "systemd" / "brainwatch.service").read_text()
    timer = (ROOT / "deploy" / "systemd" / "brainwatch.timer").read_text()
    assert "User=" not in service
    assert "brainwatch health --retain 5000" in service
    assert "NoNewPrivileges=true" in service
    assert "OnBootSec=5m" in timer
    assert "OnUnitActiveSec=6h" in timer


def test_readme_contains_install_and_first_run_commands() -> None:
    readme = (ROOT / "README.md").read_text()
    assert "uv tool install" in readme
    assert "brainwatch providers" in readme
    assert "brainwatch health" in readme
    assert "verified zero cost" in readme.lower()
