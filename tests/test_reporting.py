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
