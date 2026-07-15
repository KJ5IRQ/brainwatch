"""Brainwatch command-line interface."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="brainwatch",
        description="Model availability watchdog for verified-free endpoints.",
    )
    parser.add_argument("--version", action="store_true", help="show the installed version")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        print(f"brainwatch {__version__}")
    return 0
