"""RULES.md stays in sync with the rule catalog (Feature 14)."""

from pathlib import Path

from migration_guard.reporting import render_rules_markdown

RULES_MD = Path(__file__).resolve().parents[1] / "RULES.md"


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n")


def test_rules_md_exists_and_is_in_sync():
    assert RULES_MD.is_file(), "RULES.md is missing; regenerate with `rules --format markdown`."
    committed = _norm(RULES_MD.read_text(encoding="utf-8"))
    generated = _norm(render_rules_markdown())
    assert committed == generated, (
        "RULES.md is stale. Regenerate:\n"
        "  migration-guard rules --format markdown > RULES.md"
    )


def test_markdown_has_a_row_per_rule():
    from migration_guard.rules import rule_catalog

    md = render_rules_markdown()
    for rule in rule_catalog():
        assert f"| {rule['id']} |" in md


def test_cli_rules_markdown_matches_committed_file(capsys):
    from migration_guard.cli import main

    code = main(["rules", "--format", "markdown"])
    assert code == 0
    printed = _norm(capsys.readouterr().out)
    assert printed == _norm(RULES_MD.read_text(encoding="utf-8"))
