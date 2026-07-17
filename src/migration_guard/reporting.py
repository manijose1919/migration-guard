"""Render analysis results as text, JSON, or SARIF.

Separating rendering from analysis means new output formats never touch rule
logic — and SARIF in particular is what lets findings show up natively in the
GitHub code-scanning UI.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from . import __version__
from .models import AnalysisResult, Severity

# SARIF wants a coarse level; map our 5 severities onto its 3.
_SARIF_LEVEL = {
    Severity.INFO: "note",
    Severity.LOW: "note",
    Severity.MEDIUM: "warning",
    Severity.HIGH: "error",
    Severity.CRITICAL: "error",
}


def render_text(results: Iterable[AnalysisResult]) -> str:
    return "\n".join(r.to_text() for r in results)


def render_json(results: Iterable[AnalysisResult]) -> str:
    payload = [r.model_dump() for r in results]
    return json.dumps(payload, indent=2)


def render_sarif(results: Iterable[AnalysisResult]) -> str:
    sarif_results = []
    for r in results:
        for f in r.findings:
            sarif_results.append(
                {
                    "ruleId": f.rule_id,
                    "level": _SARIF_LEVEL[f.severity],
                    "message": {"text": f"{f.message} {f.suggestion}"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": f.filename or "<sql>"},
                                "region": {"startLine": f.line},
                            }
                        }
                    ],
                }
            )
    doc = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "MigrationGuard",
                        "version": __version__,
                        "informationUri": "https://github.com/manijose1919/migration-guard",
                    }
                },
                "results": sarif_results,
            }
        ],
    }
    return json.dumps(doc, indent=2)


# GitHub workflow-command annotation level per severity.
_GH_LEVEL = {
    Severity.INFO: "notice",
    Severity.LOW: "notice",
    Severity.MEDIUM: "warning",
    Severity.HIGH: "error",
    Severity.CRITICAL: "error",
}


def _gh_escape_data(text: str) -> str:
    # Workflow-command message data must not contain raw newlines/percent.
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _gh_escape_prop(text: str) -> str:
    return _gh_escape_data(text).replace(":", "%3A").replace(",", "%2C")


def render_github(results: Iterable[AnalysisResult]) -> str:
    """Emit ::error / ::warning / ::notice workflow commands for PR annotations."""
    lines = []
    for r in results:
        for f in r.findings:
            level = _GH_LEVEL[f.severity]
            file = _gh_escape_prop(f.filename or "<sql>")
            title = _gh_escape_prop(f.rule_id)
            body = _gh_escape_data(f"[{f.severity.value}] {f.message} {f.suggestion}")
            lines.append(
                f"::{level} file={file},line={f.line},title={title}::{body}"
            )
    return "\n".join(lines)


_RENDERERS = {
    "text": render_text,
    "json": render_json,
    "sarif": render_sarif,
    "github": render_github,
}


def render(results: Iterable[AnalysisResult], fmt: str = "text") -> str:
    try:
        renderer = _RENDERERS[fmt]
    except KeyError as err:
        raise ValueError(
            f"unknown format {fmt!r}; choose from {sorted(_RENDERERS)}"
        ) from err
    return renderer(list(results))
