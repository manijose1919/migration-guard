"""The package root re-exports the public API (Feature 16)."""

import migration_guard


def test_top_level_exports_are_available():
    # Same objects as the submodules define (a re-export, not a copy).
    import migration_guard.analyzer as analyzer_mod
    import migration_guard.models as models_mod
    from migration_guard import (
        AnalysisResult,
        Analyzer,
        Config,
        Finding,
        Severity,
    )

    assert Analyzer is analyzer_mod.Analyzer
    assert Config.__module__ == "migration_guard.config"
    assert Severity is models_mod.Severity
    assert Finding is models_mod.Finding
    assert AnalysisResult is models_mod.AnalysisResult


def test_public_api_actually_runs_from_the_root():
    result = migration_guard.Analyzer(
        migration_guard.Config(dialect="postgres")
    ).analyze_sql("CREATE INDEX i ON t (c);")
    assert result.gate_failed("HIGH")


def test_dunder_all_is_declared():
    assert set(migration_guard.__all__) >= {
        "Analyzer", "Config", "Severity", "Finding", "AnalysisResult", "__version__",
    }
