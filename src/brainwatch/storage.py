"""Runtime path construction and atomic file writes."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class StoragePaths:
    root: Path
    ledger_dir: Path
    reports_dir: Path
    backups_dir: Path
    availability_ledger: Path
    usage_ledger: Path
    latest_report: Path
    status_report: Path
    trend_report: Path
    proposed_chain: Path

    @classmethod
    def from_root(cls, root: str | Path) -> StoragePaths:
        base = Path(root).expanduser()
        ledger = base / "ledger"
        reports = base / "reports"
        return cls(
            root=base,
            ledger_dir=ledger,
            reports_dir=reports,
            backups_dir=base / "backups",
            availability_ledger=ledger / "availability.jsonl",
            usage_ledger=ledger / "usage.jsonl",
            latest_report=reports / "latest.json",
            status_report=reports / "status.txt",
            trend_report=reports / "trend.txt",
            proposed_chain=reports / "proposed-chain.json",
        )

    def ensure_writable_dirs(self) -> None:
        for directory in (self.ledger_dir, self.reports_dir, self.backups_dir):
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)


def atomic_write_text(path: str | Path, text: str, *, mode: int | None = None) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        if mode is not None:
            os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        if mode is not None:
            target.chmod(mode)
        return target
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def write_protected_text(path: str | Path, text: str) -> Path:
    return atomic_write_text(path, text, mode=0o600)
