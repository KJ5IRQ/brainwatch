#!/usr/bin/env python3
"""Fail CI when shareable files contain credential-like or machine-specific text."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple


class Finding(NamedTuple):
    path: str
    line: int
    rule: str


_RULES = (
    (
        "credential-like text",
        re.compile(
            r"(?i)(?:authorization\s*[:=]\s*bearer\s*['\"]?[A-Za-z0-9._-]{12,}|"
            r"(?:api[_-]?key|token)\s*[:=]\s*['\"][A-Za-z0-9._-]{12,}['\"]|"
            r"(?:api[_-]?key|token)\s*[:=]\s*(?:sk-|ghp_|github_pat_)[A-Za-z0-9._-]{8,})"
        ),
    ),
    (
        "private network address",
        re.compile(
            r"(?<!\d)(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
            r"192\.168\.\d{1,3}\.\d{1,3}|"
            r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(?!\d)"
        ),
    ),
    (
        "personal home path",
        re.compile(
            r"(?:/home/(?!user(?:/|$))[A-Za-z0-9._-]+/|"
            r"/Users/[A-Za-z0-9._-]+/|[A-Za-z]:\\Users\\[A-Za-z0-9._-]+\\)"
        ),
    ),
    ("private key material", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)

_SKIP_PREFIXES = ("docs/superpowers/",)


def scan_text(path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for rule, pattern in _RULES:
            if pattern.search(line):
                findings.append(Finding(path=path, line=line_number, rule=rule))
    return findings


def tracked_files(root: Path) -> list[Path]:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git executable not found")
    # Executable is resolved above; arguments and cwd are fixed by this repository.
    result = subprocess.run(  # noqa: S603
        [git, "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    names = result.stdout.decode().split("\0")
    return [
        root / name
        for name in names
        if name and not name.startswith(_SKIP_PREFIXES) and (root / name).is_file()
    ]


def scan_repository(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in tracked_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        findings.extend(scan_text(path.relative_to(root).as_posix(), text))
    return findings


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    findings = scan_repository(root)
    if not findings:
        print("sanitize-check: clean")
        return 0
    for finding in findings:
        print(f"{finding.path}:{finding.line}: {finding.rule}", file=sys.stderr)
    print(f"sanitize-check: {len(findings)} finding(s)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
