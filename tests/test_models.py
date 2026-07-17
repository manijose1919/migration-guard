import pytest

from migration_guard.models import AnalysisResult, Finding, Severity


def test_severity_ordering_and_coercion():
    assert Severity.CRITICAL > Severity.HIGH > Severity.MEDIUM > Severity.LOW > Severity.INFO
    assert Severity.HIGH >= "HIGH"
    assert Severity.HIGH >= "medium"
    assert not (Severity.LOW >= "HIGH")
    assert Severity.coerce("critical") is Severity.CRITICAL


def _finding(sev: Severity, line: int = 1) -> Finding:
    return Finding(
        rule_id="MG999",
        severity=sev,
        message="m",
        suggestion="s",
        line=line,
        statement_index=0,
    )


def test_finding_rejects_zero_line():
    with pytest.raises(ValueError):
        _finding(Severity.HIGH, line=0)


def test_result_max_severity_and_gate():
    result = AnalysisResult(
        filename="x.sql",
        findings=[_finding(Severity.MEDIUM), _finding(Severity.HIGH)],
    )
    assert result.max_severity is Severity.HIGH
    assert result.gate_failed("HIGH")
    assert not result.gate_failed("CRITICAL")
    assert result.counts() == {"MEDIUM": 1, "HIGH": 1}


def test_clean_result_has_no_gate_failure():
    result = AnalysisResult(filename="x.sql", findings=[])
    assert result.max_severity is None
    assert not result.gate_failed("INFO")
    assert "no issues" in result.to_text()


def test_to_text_contains_rule_and_suggestion():
    result = AnalysisResult(filename="x.sql", findings=[_finding(Severity.HIGH, line=7)])
    text = result.to_text()
    assert "MG999" in text
    assert "line 7" in text
    assert "-> s" in text
