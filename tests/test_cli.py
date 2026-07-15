from __future__ import annotations

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
