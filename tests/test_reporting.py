import json

import pytest

from migration_guard.analyzer import Analyzer
from migration_guard.reporting import render


@pytest.fixture
def results():
    return Analyzer().analyze_path(
        __import__("pathlib").Path(__file__).resolve().parents[1] / "examples"
    )


def test_render_text(results):
    out = render(results, "text")
    assert "MG001" in out or "MG002" in out


def test_render_text_multi_file_has_summary_footer(results):
    # The examples dir yields 2 results (dangerous + safe) -> a roll-up appears.
    out = render(results, "text")
    assert "Scanned 2 files" in out
    assert "1 with findings" in out  # only dangerous_migration.sql has findings


def test_render_text_single_file_has_no_footer():
    single = Analyzer().analyze_path(
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "examples" / "safe_migration.sql"
    )
    assert "Scanned" not in render(single, "text")


def test_render_text_all_clean_multi_file_footer(tmp_path):
    (tmp_path / "a.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "b.sql").write_text("SELECT 2;", encoding="utf-8")
    out = render(Analyzer().analyze_path(tmp_path), "text")
    assert "Scanned 2 files, 0 with findings." in out
    assert "0 findings." in out


def test_render_json_is_valid(results):
    out = render(results, "json")
    parsed = json.loads(out)
    assert isinstance(parsed, list)
    assert any("findings" in doc for doc in parsed)


def test_render_sarif_structure(results):
    out = render(results, "sarif")
    doc = json.loads(out)
    assert doc["version"] == "2.1.0"
    assert doc["runs"][0]["tool"]["driver"]["name"] == "MigrationGuard"
    # every finding maps to a sarif result with a level
    for r in doc["runs"][0]["results"]:
        assert r["level"] in {"note", "warning", "error"}


def test_unknown_format_raises(results):
    with pytest.raises(ValueError):
        render(results, "xml")
