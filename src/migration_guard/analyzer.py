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
from .suppressions import parse_directives


class Analyzer:
    """Runs a rule set over SQL and produces :class:`AnalysisResult`s."""

    def __init__(self, config: Config | None = None, rules: list[Rule] | None = None):
        self.config = config or Config()
        all_rules = rules if rules is not None else default_rules()
        # Honor the disabled-rules policy and the target dialect up front.
        self.rules = [
            r
            for r in all_rules
            if r.id not in self.config.disabled_rules
            and r.applies_to(self.config.dialect)
        ]

    def analyze_sql(self, sql: str, filename: str | None = None) -> AnalysisResult:
        suppressions = parse_directives(sql)
        findings: list[Finding] = []
        for stmt in parse_sql(sql):
            for rule in self.rules:
                for finding in rule.check(stmt, self.config):
                    if suppressions.is_suppressed(finding.rule_id, finding.line):
                        continue
                    finding.filename = filename
                    finding.fix = rule.fix(stmt)
                    findings.append(finding)
        # Most severe first, then by source order.
        findings.sort(key=lambda f: (-f.severity.order, f.line, f.statement_index))
        return AnalysisResult(filename=filename, findings=findings)

    def apply_fixes(self, sql: str) -> tuple[str, int]:
        """Rewrite ``sql`` applying every safe automatic fix.

        Only statements that a rule both *flags* and offers a fix for are
        rewritten, and only when not suppressed. Edits replace the exact source
        span, so untouched statements, comments, and formatting are preserved.
        Returns the new SQL and the number of fixes applied.
        """
        suppressions = parse_directives(sql)
        edits: list[tuple[int, int, str]] = []
        for stmt in parse_sql(sql):
            for rule in self.rules:
                if suppressions.is_suppressed(rule.id, stmt.line):
                    continue
                if not rule.check(stmt, self.config):
                    continue
                fixed = rule.fix(stmt)
                if fixed is not None and fixed != stmt.source:
                    edits.append((stmt.start, stmt.start + len(stmt.source), fixed))
                    break  # at most one fix per statement
        new_sql = sql
        # Apply back-to-front so earlier offsets stay valid.
        for start, end, text in sorted(edits, reverse=True):
            new_sql = new_sql[:start] + text + new_sql[end:]
        return new_sql, len(edits)

    def fix_file(self, path: str | Path) -> int:
        """Apply fixes to ``path`` in place; return the number applied."""
        p = Path(path)
        original = p.read_text(encoding="utf-8")
        new_sql, count = self.apply_fixes(original)
        if count and new_sql != original:
            p.write_text(new_sql, encoding="utf-8")
        return count

    def analyze_file(self, path: str | Path) -> AnalysisResult:
        p = Path(path)
        return self.analyze_sql(p.read_text(encoding="utf-8"), filename=str(p))

    def analyze_path(self, path: str | Path) -> list[AnalysisResult]:
        """Analyze a single ``.sql`` file or every ``.sql`` file under a dir."""
        p = Path(path)
        if p.is_dir():
            return [self.analyze_file(f) for f in sorted(p.rglob("*.sql"))]
        return [self.analyze_file(p)]
