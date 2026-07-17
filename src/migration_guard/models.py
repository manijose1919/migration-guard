"""Core data models: Severity, Finding, AnalysisResult.

These are the vocabulary every other module speaks. Keeping them free of any
parsing / IO logic is what lets the analyzer be embedded as a plain library.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

# Ordered from least to most severe. The index defines comparability.
_ORDER: dict[str, int] = {
    "INFO": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


class Severity(str, Enum):
    """A comparable severity level.

    Subclasses ``str`` so it serializes to its name in JSON, but overrides the
    ordering operators so callers can write ``finding.severity >= "HIGH"``.
    """

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def order(self) -> int:
        return _ORDER[self.value]

    @classmethod
    def coerce(cls, value: Severity | str) -> Severity:
        if isinstance(value, cls):
            return value
        return cls(str(value).strip().upper())

    # Ordering compares by rank, and coerces plain strings for ergonomic gates.
    def __lt__(self, other: object) -> bool:
        return self.order < Severity.coerce(other).order  # type: ignore[arg-type]

    def __le__(self, other: object) -> bool:
        return self.order <= Severity.coerce(other).order  # type: ignore[arg-type]

    def __gt__(self, other: object) -> bool:
        return self.order > Severity.coerce(other).order  # type: ignore[arg-type]

    def __ge__(self, other: object) -> bool:
        return self.order >= Severity.coerce(other).order  # type: ignore[arg-type]


class Finding(BaseModel):
    """A single safety concern detected in one SQL statement."""

    rule_id: str
    severity: Severity
    message: str
    suggestion: str
    line: int = Field(ge=1)
    statement_index: int = Field(ge=0)
    filename: str | None = None


class AnalysisResult(BaseModel):
    """The outcome of analyzing one SQL document."""

    filename: str | None = None
    findings: list[Finding] = Field(default_factory=list)

    @property
    def max_severity(self) -> Severity | None:
        """Highest severity among findings, or ``None`` when clean."""
        if not self.findings:
            return None
        return max((f.severity for f in self.findings), key=lambda s: s.order)

    def counts(self) -> dict[str, int]:
        """Number of findings per severity label (only non-zero entries)."""
        out: dict[str, int] = {}
        for f in self.findings:
            out[f.severity.value] = out.get(f.severity.value, 0) + 1
        return out

    def gate_failed(self, threshold: Severity | str) -> bool:
        """True when any finding meets or exceeds ``threshold`` (the CI gate)."""
        thr = Severity.coerce(threshold)
        return any(f.severity >= thr for f in self.findings)

    def to_text(self) -> str:
        """Human-readable report for a single document."""
        header = self.filename or "<sql>"
        if not self.findings:
            return f"{header}\n  OK  no issues found\n"
        lines = [header]
        for f in self.findings:
            lines.append(
                f"  {f.severity.value:<8} {f.rule_id}  line {f.line}  {f.message}"
            )
            lines.append(f"{'':>27}-> {f.suggestion}")
        counts = ", ".join(f"{n} {sev}" for sev, n in self.counts().items())
        lines.append(f"\n{len(self.findings)} findings ({counts}).")
        return "\n".join(lines) + "\n"
