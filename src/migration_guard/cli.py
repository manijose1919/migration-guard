"""Command-line interface.

The exit code is the contract that makes this usable as a CI gate:
    0  -> no finding met the fail-on threshold
    1  -> at least one finding met/exceeded the threshold
    2  -> usage / input error (e.g. path not found)
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .analyzer import Analyzer
from .config import SUPPORTED_DIALECTS, resolve_config
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
        "--dialect", choices=list(SUPPORTED_DIALECTS), default=None,
        help="Target SQL dialect (default: env MG_DIALECT or postgres).",
    )
    fix_mode = analyze.add_mutually_exclusive_group()
    fix_mode.add_argument(
        "--fix", action="store_true",
        help="Rewrite file(s) in place, applying safe automatic fixes, then re-analyze.",
    )
    fix_mode.add_argument(
        "--diff", action="store_true",
        help="Preview autofixes as a unified diff without writing; exit 1 if any fix is pending.",
    )
    analyze.add_argument(
        "--config", default=None,
        help="Path to a .migrationguard.toml (default: auto-discover upward).",
    )

    rules_parser = sub.add_parser("rules", help="List the available safety rules.")
    rules_parser.add_argument(
        "-f", "--format", choices=["text", "json"], default="text",
        help="Output format for the rule catalog (default: text).",
    )
    return parser


def _config_from_args(args: argparse.Namespace):
    """Layer config sources: file -> env -> CLI flags (highest wins)."""
    overrides = {
        "fail_on": Severity.coerce(args.fail_on) if args.fail_on else None,
        "large_tables": args.large_tables,
        "disabled_rules": args.disable,
        "dialect": args.dialect,
    }
    return resolve_config(config_path=args.config, overrides=overrides)


def _sql_files(path: str) -> list[Path]:
    """Every ``.sql`` file under ``path`` (or the file itself)."""
    p = Path(path)
    return sorted(p.rglob("*.sql")) if p.is_dir() else [p]


def _run_diff(analyzer: Analyzer, paths: Sequence[str]) -> int:
    """Print a unified diff of pending autofixes; write nothing. Exit 1 if any."""
    changed = False
    for path in paths:
        for f in _sql_files(path):
            try:
                original = f.read_text(encoding="utf-8")
            except (FileNotFoundError, NotADirectoryError) as err:
                print(f"error: {err}", file=sys.stderr)
                return 2
            new_sql, count = analyzer.apply_fixes(original)
            if count and new_sql != original:
                changed = True
                sys.stdout.writelines(
                    difflib.unified_diff(
                        original.splitlines(keepends=True),
                        new_sql.splitlines(keepends=True),
                        fromfile=str(f),
                        tofile=f"{f} (fixed)",
                    )
                )
    return 1 if changed else 0


def _run_analyze(args: argparse.Namespace) -> int:
    cfg = _config_from_args(args)
    analyzer = Analyzer(cfg)

    if args.diff:
        return _run_diff(analyzer, args.paths)

    if args.fix:
        fixed_total = 0
        for path in args.paths:
            try:
                for f in _sql_files(path):
                    fixed_total += analyzer.fix_file(f)
            except (FileNotFoundError, NotADirectoryError) as err:
                print(f"error: {err}", file=sys.stderr)
                return 2
        print(f"Applied {fixed_total} automatic fix(es).", file=sys.stderr)

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


def _run_rules(fmt: str = "text") -> int:
    catalog = rule_catalog()
    if fmt == "json":
        print(json.dumps(catalog, indent=2))
        return 0
    for rule in catalog:
        dialects = ",".join(rule["dialects"])
        fixable = " (fixable)" if rule["fixable"] else ""
        print(
            f"{rule['id']}  {rule['default_severity']:<8} {rule['name']:<28} "
            f"[{dialects}]{fixable}"
        )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "analyze":
        return _run_analyze(args)
    if args.command == "rules":
        return _run_rules(args.format)
    return 2  # pragma: no cover - argparse enforces a valid command


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
