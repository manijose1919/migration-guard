"""MigrationGuard — static safety analyzer for SQL database migrations."""

__version__ = "0.1.0"

# Public API re-exports so integrators can `from migration_guard import Analyzer`.
# Placed after __version__ because submodules read it during import.
from .analyzer import Analyzer  # noqa: E402
from .config import Config  # noqa: E402
from .models import AnalysisResult, Finding, Severity  # noqa: E402

__all__ = [
    "Analyzer",
    "Config",
    "Severity",
    "Finding",
    "AnalysisResult",
    "__version__",
]
