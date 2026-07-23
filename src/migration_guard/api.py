"""FastAPI application exposing the analyzer as a microservice.

This is a thin adapter: it validates input, builds a per-request Config, and
delegates to the same Analyzer used by the CLI and the library. No rule logic
lives here.
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field, field_validator

from . import __version__
from .analyzer import Analyzer
from .config import SUPPORTED_DIALECTS, Config
from .models import Finding, Severity
from .rules import rule_catalog

app = FastAPI(
    title="MigrationGuard",
    version=__version__,
    description="Static safety analyzer for SQL database migrations.",
)


class AnalyzeRequest(BaseModel):
    sql: str = Field(..., description="Raw SQL migration text to analyze.")
    filename: str | None = Field(None, description="Optional name for reporting.")
    fail_on: Severity = Field(Severity.HIGH, description="Gate threshold.")
    large_tables: list[str] = Field(default_factory=list)
    disabled_rules: list[str] = Field(default_factory=list)
    dialect: str = Field("postgres", description="Target SQL dialect.")

    @field_validator("dialect")
    @classmethod
    def _known_dialect(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in SUPPORTED_DIALECTS:
            raise ValueError(
                f"unknown dialect {value!r}; choose one of {', '.join(SUPPORTED_DIALECTS)}"
            )
        return normalized


class AnalyzeResponse(BaseModel):
    filename: str | None
    findings: list[Finding]
    max_severity: Severity | None
    gate_failed: bool
    counts: dict[str, int]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/rules")
def rules() -> list[dict]:
    return rule_catalog()


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    config = Config(
        fail_on=req.fail_on,
        large_tables=set(req.large_tables),
        disabled_rules=set(req.disabled_rules),
        dialect=req.dialect,
    )
    result = Analyzer(config).analyze_sql(req.sql, filename=req.filename)
    return AnalyzeResponse(
        filename=result.filename,
        findings=result.findings,
        max_severity=result.max_severity,
        gate_failed=result.gate_failed(config.fail_on),
        counts=result.counts(),
    )
