from pathlib import Path

from migration_guard.analyzer import Analyzer
from migration_guard.models import Severity

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_dangerous_example_flags_all_five_rules():
    result = Analyzer().analyze_file(EXAMPLES / "dangerous_migration.sql")
    ids = {f.rule_id for f in result.findings}
    assert {"MG001", "MG002", "MG003", "MG005", "MG007"} <= ids
    assert result.max_severity is Severity.HIGH
    assert result.gate_failed("HIGH")


def test_safe_example_is_clean():
    result = Analyzer().analyze_file(EXAMPLES / "safe_migration.sql")
    assert result.findings == []
    assert not result.gate_failed("INFO")


def test_findings_sorted_most_severe_first():
    result = Analyzer().analyze_file(EXAMPLES / "dangerous_migration.sql")
    orders = [f.severity.order for f in result.findings]
    assert orders == sorted(orders, reverse=True)


def test_filename_is_attached_to_findings():
    result = Analyzer().analyze_sql("DROP TABLE t;", filename="m.sql")
    # DROP TABLE isn't one of our column rules, so assert on a known dangerous op:
    result = Analyzer().analyze_sql("CREATE INDEX i ON t (c);", filename="m.sql")
    assert all(f.filename == "m.sql" for f in result.findings)


def test_analyze_path_on_directory(tmp_path):
    (tmp_path / "a.sql").write_text("CREATE INDEX i ON t (c);", encoding="utf-8")
    (tmp_path / "b.sql").write_text("SELECT 1;", encoding="utf-8")
    results = Analyzer().analyze_path(tmp_path)
    assert len(results) == 2
    total = sum(len(r.findings) for r in results)
    assert total == 1
