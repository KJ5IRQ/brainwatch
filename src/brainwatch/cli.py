"""Brainwatch command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .config import ConfigError, Settings, load_settings
from .health import run_health
from .storage import StoragePaths
from .trend import load_usage, rank_by_instability, stability, write_report


class CommandError(RuntimeError):
    """Raised for an actionable local CLI failure."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="brainwatch",
        description="Model availability watchdog for verified-free endpoints.",
    )
    parser.add_argument("--version", action="store_true", help="show the installed version")
    parser.add_argument("--config", help="path to config.toml")
    parser.add_argument("--data-dir", help="runtime evidence directory")
    subparsers = parser.add_subparsers(dest="command")

    providers = subparsers.add_parser("providers", help="list configured providers")
    providers.add_argument("--json", action="store_true", help="emit JSON")

    health = subparsers.add_parser("health", help="discover and probe verified-free models")
    health.add_argument("--provider", action="append", default=[], help="provider name")
    health.add_argument("--top", type=int, default=3, help="maximum proposed chain length")
    health.add_argument("--retain", type=int, help="retain newest ledger records")
    health.add_argument("--json", action="store_true", help="emit JSON")

    status = subparsers.add_parser("status", help="show the latest health report")
    status.add_argument("--json", action="store_true", help="emit JSON")

    subparsers.add_parser("trend", help="show historical reliability")

    chain = subparsers.add_parser("chain", help="show the proposed chain")
    chain.add_argument("--format", choices=("json", "openclaw"), default="json")
    return parser


def _settings(args: argparse.Namespace) -> Settings:
    return load_settings(path=args.config, data_dir=args.data_dir)


def _read_json(path: Path) -> object:
    if not path.is_file():
        raise CommandError(f"evidence file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CommandError(f"invalid JSON evidence file: {path}") from exc


def _providers(args: argparse.Namespace) -> int:
    settings = _settings(args)
    rows = [
        {
            "name": provider.name,
            "kind": provider.kind,
            "base_url": provider.base_url,
            "api_key_env": provider.api_key_env,
            "explicit_free_models": len(provider.free_models),
        }
        for provider in settings.providers
    ]
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        for row in rows:
            print(
                f"{row['name']}\t{row['kind']}\t{row['base_url']}\t"
                f"key_env={row['api_key_env']}"
            )
    return 0


def _health(args: argparse.Namespace) -> int:
    outcome = run_health(
        _settings(args),
        provider_names=tuple(args.provider),
        top=args.top,
        retain=args.retain,
    )
    if args.json:
        print(json.dumps(outcome.report, indent=2, sort_keys=True))
    else:
        print(outcome.paths.status_report.read_text(encoding="utf-8"), end="")
    for name, summary in outcome.report.get("providers", {}).items():
        error = summary.get("error") if isinstance(summary, dict) else None
        if error:
            print(f"provider {name}: {error}", file=sys.stderr)
    return outcome.exit_code


def _status(args: argparse.Namespace) -> int:
    settings = _settings(args)
    paths = StoragePaths.from_root(settings.data_dir)
    if args.json:
        print(json.dumps(_read_json(paths.latest_report), indent=2, sort_keys=True))
    else:
        if not paths.status_report.is_file():
            raise CommandError(f"evidence file not found: {paths.status_report}")
        print(paths.status_report.read_text(encoding="utf-8"), end="")
    return 0


def _trend(args: argparse.Namespace) -> int:
    settings = _settings(args)
    paths = StoragePaths.from_root(settings.data_dir)
    stats = stability(load_usage(paths.usage_ledger))
    text = write_report(stats, rank_by_instability(stats), path=paths.trend_report)
    print(text, end="")
    return 0


def _chain(args: argparse.Namespace) -> int:
    settings = _settings(args)
    paths = StoragePaths.from_root(settings.data_dir)
    chain = _read_json(paths.proposed_chain)
    if not isinstance(chain, list):
        raise CommandError("proposed chain evidence must be a JSON list")
    if args.format == "json":
        print(json.dumps(chain, indent=2, sort_keys=True))
    else:
        mapped = [f"{item['provider']}/{item['model_id']}" for item in chain]
        output = {"primary": mapped[0] if mapped else None, "fallbacks": mapped[1:]}
        print(json.dumps(output, indent=2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(f"brainwatch {__version__}")
        return 0
    handlers = {
        "providers": _providers,
        "health": _health,
        "status": _status,
        "trend": _trend,
        "chain": _chain,
    }
    if args.command is None:
        parser.print_help()
        return 0
    try:
        return handlers[args.command](args)
    except (CommandError, ConfigError, OSError, RuntimeError) as exc:
        print(f"brainwatch: {exc}", file=sys.stderr)
        return 1
