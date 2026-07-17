"""The orchestration core: parse a document, run every rule, collect findings.

This class has no CLI/HTTP/file concerns beyond an optional path helper, so it
embeds cleanly as a library (see the Integration guide in the README).
"""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .models import AnalysisResult, Finding
from .parser import parse_sql
from .rules import Rule, default_rules


class Analyzer:
    """Runs a rule set over SQL and produces :class:`AnalysisResult`s."""

    def __init__(self, config: Config | None = None, rules: list[Rule] | None = None):
        self.config = config or Config()
        all_rules = rules if rules is not None else default_rules()
        # Honor the disabled-rules policy up front.
        self.rules = [r for r in all_rules if r.id not in self.config.disabled_rules]

    def analyze_sql(self, sql: str, filename: str | None = None) -> AnalysisResult:
        findings: list[Finding] = []
        for stmt in parse_sql(sql):
            for rule in self.rules:
                for finding in rule.check(stmt, self.config):
                    finding.filename = filename
                    findings.append(finding)
        # Most severe first, then by source order.
        findings.sort(key=lambda f: (-f.severity.order, f.line, f.statement_index))
        return AnalysisResult(filename=filename, findings=findings)

    def analyze_file(self, path: str | Path) -> AnalysisResult:
        p = Path(path)
        return self.analyze_sql(p.read_text(encoding="utf-8"), filename=str(p))

    def analyze_path(self, path: str | Path) -> list[AnalysisResult]:
        """Analyze a single ``.sql`` file or every ``.sql`` file under a dir."""
        p = Path(path)
        if p.is_dir():
            return [self.analyze_file(f) for f in sorted(p.rglob("*.sql"))]
        return [self.analyze_file(p)]
