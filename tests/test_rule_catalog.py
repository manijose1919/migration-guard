"""Rich rule catalog metadata (Feature 13)."""

import json

from migration_guard.cli import main
from migration_guard.rules import rule_catalog


def _by_id() -> dict[str, dict]:
    return {r["id"]: r for r in rule_catalog()}


def test_catalog_entries_have_rich_metadata():
    entry = _by_id()["MG001"]
    assert set(entry) >= {"id", "name", "default_severity", "summary", "dialects", "fixable"}
    assert entry["summary"]  # non-empty one-liner


def test_fixable_flag_reflects_fix_override():
    cat = _by_id()
    assert cat["MG002"]["fixable"] is True   # adds CONCURRENTLY
    assert cat["MG001"]["fixable"] is False  # multi-step, no autofix


def test_dialects_are_reported_and_sorted():
    cat = _by_id()
    assert cat["MG014"]["dialects"] == ["postgres"]
    assert cat["MG015"]["dialects"] == ["mysql"]
    assert cat["MG013"]["dialects"] == ["mysql", "postgres"]  # universal, sorted


def test_rules_json_format_is_valid_and_complete(capsys):
    code = main(["rules", "--format", "json"])
    assert code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert {r["id"] for r in parsed} == {f"MG{n:03d}" for n in range(1, len(parsed) + 1)}


def test_rules_text_format_marks_fixable(capsys):
    code = main(["rules"])
    out = capsys.readouterr().out
    assert code == 0
    # The fixable marker appears somewhere for a known fixable rule line.
    fixable_line = next(line for line in out.splitlines() if line.startswith("MG002"))
    assert "fixable" in fixable_line
