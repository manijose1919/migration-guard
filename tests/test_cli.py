import json
from pathlib import Path

import pytest

from migration_guard.cli import main

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
DANGEROUS = str(EXAMPLES / "dangerous_migration.sql")
SAFE = str(EXAMPLES / "safe_migration.sql")


def test_analyze_dangerous_fails_gate(capsys):
    code = main(["analyze", DANGEROUS])
    out = capsys.readouterr().out
    assert code == 1
    assert "MG001" in out


def test_analyze_safe_passes(capsys):
    code = main(["analyze", SAFE])
    assert code == 0


def test_json_format_is_valid(capsys):
    code = main(["analyze", DANGEROUS, "--format", "json"])
    out = capsys.readouterr().out
    assert code == 1
    json.loads(out)  # must parse


def test_fail_on_critical_passes_when_only_high(capsys):
    # The dangerous example maxes out at HIGH, so a CRITICAL gate passes.
    code = main(["analyze", DANGEROUS, "--fail-on", "CRITICAL"])
    assert code == 0


def test_disable_rule_via_flag(capsys):
    code = main(["analyze", DANGEROUS, "--disable", "MG001,MG002,MG005,MG007"])
    out = capsys.readouterr().out
    # Only MG003 (MEDIUM) remains, which is below the default HIGH gate.
    assert code == 0
    assert "MG001" not in out


def test_large_tables_escalation_changes_gate(tmp_path, capsys):
    f = tmp_path / "m.sql"
    f.write_text("ALTER TABLE users DROP COLUMN old;", encoding="utf-8")  # MG003 MEDIUM
    # Default gate HIGH: MEDIUM passes.
    assert main(["analyze", str(f)]) == 0
    # Mark users large -> MG003 escalates to HIGH -> gate fails.
    assert main(["analyze", str(f), "--large-tables", "users"]) == 1


def test_rules_subcommand(capsys):
    code = main(["rules"])
    out = capsys.readouterr().out
    assert code == 0
    assert "MG001" in out


def test_missing_path_returns_2(capsys):
    code = main(["analyze", "does_not_exist.sql"])
    assert code == 2
