from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_sanitizer():
    path = ROOT / "scripts" / "sanitize_check.py"
    spec = importlib.util.spec_from_file_location("sanitize_check", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sanitizer_detects_secrets_private_addresses_and_personal_paths() -> None:
    sanitizer = load_sanitizer()
    unsafe = "Authorization: Bearer abcdefghijklmnop\nserver=192.168.50.5\n/home/alice/app"
    findings = sanitizer.scan_text("unsafe.txt", unsafe)
    assert {finding.rule for finding in findings} == {
        "credential-like text",
        "private network address",
        "personal home path",
    }
    assert sanitizer.scan_text("safe.txt", "https://models.example.test\n/home/user/example") == []


def test_ci_checks_supported_python_versions_and_wheel_install() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    for version in ("3.11", "3.12", "3.13"):
        assert version in workflow
    assert "uv sync --locked --extra dev" in workflow
    assert "scripts/sanitize_check.py" in workflow
    assert "uv build" in workflow
    assert "brainwatch --version" in workflow


def test_repository_metadata_exists() -> None:
    required = [
        ROOT / ".github" / "CODEOWNERS",
        ROOT / ".github" / "dependabot.yml",
        ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml",
        ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml",
        ROOT / ".github" / "pull_request_template.md",
    ]
    assert all(path.is_file() for path in required)
