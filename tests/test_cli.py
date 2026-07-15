from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    from brainwatch.cli import main

    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "brainwatch 0.1.0"


def test_help(capsys: pytest.CaptureFixture[str]) -> None:
    from brainwatch.cli import main

    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "Model availability watchdog" in capsys.readouterr().out


def write_config(path: Path) -> Path:
    path.write_text(
        """
[[providers]]
name = "friend"
kind = "openai-compatible"
base_url = "https://models.example.test"
api_key_env = "FRIEND_API_KEY"
free_models = ["free"]
"""
    )
    return path


def test_providers_lists_config_without_needing_secret(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from brainwatch.cli import main

    config = write_config(tmp_path / "config.toml")
    assert main(["--config", str(config), "providers"]) == 0
    assert "friend" in capsys.readouterr().out


def test_status_trend_and_chain_read_local_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from brainwatch.cli import main

    config = write_config(tmp_path / "config.toml")
    state = tmp_path / "state"
    reports = state / "reports"
    ledger = state / "ledger"
    reports.mkdir(parents=True)
    ledger.mkdir(parents=True)
    latest = {
        "generated_at": 1,
        "passed": 1,
        "proposed_chain": [{"provider": "friend", "model_id": "free"}],
    }
    (reports / "latest.json").write_text(json.dumps(latest))
    (reports / "status.txt").write_text("healthy\n")
    (reports / "proposed-chain.json").write_text(json.dumps(latest["proposed_chain"]))
    (ledger / "usage.jsonl").write_text(
        json.dumps(
            {
                "provider": "friend",
                "model_id": "free",
                "timestamp": 1,
                "status": "ok",
            }
        )
        + "\n"
    )

    base = ["--config", str(config), "--data-dir", str(state)]
    assert main([*base, "status", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["passed"] == 1
    assert main([*base, "trend"]) == 0
    assert "friend:free" in capsys.readouterr().out
    assert main([*base, "chain", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["model_id"] == "free"


def test_health_missing_key_names_variable_without_secret_value(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from brainwatch.cli import main

    config = write_config(tmp_path / "config.toml")
    state = tmp_path / "state"
    assert main(["--config", str(config), "--data-dir", str(state), "health"]) == 2
    captured = capsys.readouterr()
    assert "FRIEND_API_KEY" in captured.err
    assert "secret-value" not in captured.err


def test_openclaw_apply_requires_yes_and_then_updates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from brainwatch.cli import main

    state = tmp_path / "state"
    reports = state / "reports"
    reports.mkdir(parents=True)
    (reports / "proposed-chain.json").write_text(
        json.dumps([{"provider": "friend", "model_id": "free"}])
    )
    target = tmp_path / "openclaw.json"
    target.write_text(
        json.dumps(
            {
                "agents": {
                    "defaults": {
                        "model": {"primary": "old/model", "fallbacks": []}
                    }
                }
            }
        )
    )
    command = [
        "--data-dir",
        str(state),
        "openclaw",
        "apply",
        "--config",
        str(target),
    ]
    assert main(command) == 1
    assert "--yes" in capsys.readouterr().err
    assert main([*command, "--yes"]) == 0
    capsys.readouterr()
    model = json.loads(target.read_text())["agents"]["defaults"]["model"]
    assert model == {"primary": "friend/free", "fallbacks": []}
