"""Command-line interface.

The exit code is the contract that makes this usable as a CI gate:
    0  -> no finding met the fail-on threshold
    1  -> at least one finding met/exceeded the threshold
    2  -> usage / input error (e.g. path not found)
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .analyzer import Analyzer
from .config import resolve_config
from .models import Severity
from .reporting import render
from .rules import rule_catalog

_SEVERITY_CHOICES = [s.value for s in Severity]


def _csv(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="migration-guard",
        description="Static safety analyzer for SQL database migrations.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="Analyze SQL migration file(s) or directory.")
    analyze.add_argument("paths", nargs="+", help="SQL files or directories to scan.")
    analyze.add_argument(
        "-f", "--format", choices=["text", "json", "sarif", "github"], default="text",
        help="Output format (default: text). 'github' emits PR annotations.",
    )
    analyze.add_argument(
        "--fail-on", choices=_SEVERITY_CHOICES, default=None,
        help="Severity that triggers a non-zero exit (default: env MG_FAIL_ON or HIGH).",
    )
    analyze.add_argument(
        "--large-tables", type=_csv, default=None,
        help="Comma-separated high-traffic tables; locking ops on them escalate.",
    )
    analyze.add_argument(
        "--disable", type=_csv, default=None,
        help="Comma-separated rule IDs to skip (e.g. MG001,MG003).",
    )
    analyze.add_argument(
        "--config", default=None,
        help="Path to a .migrationguard.toml (default: auto-discover upward).",
    )

    sub.add_parser("rules", help="List the available safety rules.")
    return parser


def _config_from_args(args: argparse.Namespace):
    """Layer config sources: file -> env -> CLI flags (highest wins)."""
    overrides = {
        "fail_on": Severity.coerce(args.fail_on) if args.fail_on else None,
        "large_tables": args.large_tables,
        "disabled_rules": args.disable,
    }
    return resolve_config(config_path=args.config, overrides=overrides)


def _run_analyze(args: argparse.Namespace) -> int:
    cfg = _config_from_args(args)
    analyzer = Analyzer(cfg)

    results = []
    for path in args.paths:
        try:
            results.extend(analyzer.analyze_path(path))
        except (FileNotFoundError, NotADirectoryError) as err:
            print(f"error: {err}", file=sys.stderr)
            return 2

    print(render(results, args.format))

    gate_failed = any(r.gate_failed(cfg.fail_on) for r in results)
    if gate_failed and args.format == "text":
        print(f"Gate = {cfg.fail_on.value} -> FAILED", file=sys.stderr)
    return 1 if gate_failed else 0


def _run_rules() -> int:
    for rule in rule_catalog():
        print(f"{rule['id']}  {rule['default_severity']:<8} {rule['name']}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "analyze":
        return _run_analyze(args)
    if args.command == "rules":
        return _run_rules()
    return 2  # pragma: no cover - argparse enforces a valid command


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
