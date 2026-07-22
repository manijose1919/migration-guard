"""Rule interface and shared helpers.

Every safety check is a small, isolated :class:`Rule`. The analyzer never knows
what a rule does — it just calls ``check``. That is the seam an enterprise
extends without touching the core.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import SUPPORTED_DIALECTS, Config
from ..models import Finding, Severity
from ..parser import Statement


class Rule(ABC):
    """Base class for a single migration-safety check."""

    #: Stable identifier, e.g. ``"MG001"``. Used for disabling and reporting.
    id: str
    #: Short human name.
    name: str
    #: Severity used when the config does not escalate.
    default_severity: Severity
    #: Dialects this rule applies to. Defaults to every supported dialect;
    #: rules whose advice is dialect-specific narrow this (e.g. Postgres-only).
    dialects: frozenset[str] = frozenset(SUPPORTED_DIALECTS)

    def applies_to(self, dialect: str) -> bool:
        return dialect in self.dialects

    @abstractmethod
    def check(self, stmt: Statement, config: Config) -> list[Finding]:
        """Return zero or more findings for a single statement."""
        raise NotImplementedError

    def fix(self, stmt: Statement) -> str | None:
        """Return a safe rewritten form of ``stmt.source``, or ``None``.

        Default: no automatic fix. Only rules with a correct *single-statement*
        rewrite override this; anything needing a multi-step expand/contract or
        a human decision must stay ``None``.
        """
        return None

    # -- helpers shared by concrete rules --------------------------------

    def _severity_for(self, stmt: Statement, config: Config) -> Severity:
        """Escalate one level when the statement targets a 'large' table."""
        base = self.default_severity
        if config.is_large(stmt.table) and base < Severity.CRITICAL:
            return Severity(list(Severity)[base.order + 1].value)
        return base

    def _finding(
        self,
        stmt: Statement,
        config: Config,
        message: str,
        suggestion: str,
    ) -> Finding:
        return Finding(
            rule_id=self.id,
            severity=self._severity_for(stmt, config),
            message=message,
            suggestion=suggestion,
            line=stmt.line,
            statement_index=stmt.index,
        )
