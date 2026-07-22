"""H-6.9.4 Alternative E — diagnostic log projection (P) derived from report (R).

Pure, read-only, deterministic, one-way. Never feeds runtime engines.
Schema: docs/H693_DIAGNOSTIC_REPRESENTATION_CERTIFICATION_PLAN.md v1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hotirjam_ai5.objective.objective_snapshot import ObjectiveSnapshot
from hotirjam_ai5.objective_diagnostics.models import (
    LifecycleState,
    ObjectiveAuditReport,
    SwingDiagnostic,
)

DIAGNOSTIC_LOG_VERSION = 1
DIAGNOSTIC_LOG_SOURCE = "objective_audit_report"
_SUMMARY_HEAD_MAX = 32
_TOP_K = 5

_REQUIRED_BODY_FIELDS: frozenset[str] = frozenset(
    {
        "source",
        "hierarchy_version",
        "registry_size",
        "transition_count",
        "checkpoint_version",
        "timestamp",
        "current_price",
        "tick_size",
        "high_count",
        "low_count",
        "eligible_high_count",
        "eligible_low_count",
        "challenged_count",
        "summary_line_count",
        "selected_high",
        "selected_low",
    }
)
_FORBIDDEN_DIAGNOSTIC_KEYS: frozenset[str] = frozenset(
    {
        "highs",
        "lows",
        "objective_diagnostics",
    }
)


@dataclass(frozen=True, slots=True)
class CompactSwingRef:
    """Compact swing row for projection (optional top-K / selected refs)."""

    swing_id: int
    price: float
    lifecycle: str
    eligible: bool
    category: str | None = None
    distance_ticks: float | None = None
    challenge_state: str | None = None

    def as_selected_dict(self) -> dict[str, Any]:
        return {
            "swing_id": self.swing_id,
            "price": self.price,
            "lifecycle": self.lifecycle,
            "eligible": self.eligible,
        }

    def as_compact_dict(self) -> dict[str, Any]:
        return {
            "swing_id": self.swing_id,
            "price": self.price,
            "lifecycle": self.lifecycle,
            "category": self.category,
            "eligible": self.eligible,
            "distance_ticks": self.distance_ticks,
            "challenge_state": self.challenge_state,
        }


@dataclass(frozen=True, slots=True)
class DiagnosticLogProjection:
    """Projection P — logger / IDC summary representation (schema v1)."""

    diagnostic_log_version: int
    source: str
    hierarchy_version: int
    registry_size: int
    transition_count: int
    checkpoint_version: int
    timestamp: float
    current_price: float
    tick_size: float
    high_count: int
    low_count: int
    eligible_high_count: int
    eligible_low_count: int
    challenged_count: int
    summary_line_count: int
    selected_high: CompactSwingRef | None
    selected_low: CompactSwingRef | None
    # Optional v1
    summary_lines_head: tuple[str, ...] = ()
    top_eligible_highs: tuple[CompactSwingRef, ...] = ()
    top_eligible_lows: tuple[CompactSwingRef, ...] = ()

    def diagnostic_log_body(self) -> dict[str, Any]:
        """Body object under ``diagnostic_log`` (excludes envelope version)."""
        body: dict[str, Any] = {
            "source": self.source,
            "hierarchy_version": self.hierarchy_version,
            "registry_size": self.registry_size,
            "transition_count": self.transition_count,
            "checkpoint_version": self.checkpoint_version,
            "timestamp": self.timestamp,
            "current_price": self.current_price,
            "tick_size": self.tick_size,
            "high_count": self.high_count,
            "low_count": self.low_count,
            "eligible_high_count": self.eligible_high_count,
            "eligible_low_count": self.eligible_low_count,
            "challenged_count": self.challenged_count,
            "summary_line_count": self.summary_line_count,
            "selected_high": (
                None
                if self.selected_high is None
                else self.selected_high.as_selected_dict()
            ),
            "selected_low": (
                None if self.selected_low is None else self.selected_low.as_selected_dict()
            ),
            "summary_lines_head": list(self.summary_lines_head),
            "top_eligible_highs": [row.as_compact_dict() for row in self.top_eligible_highs],
            "top_eligible_lows": [row.as_compact_dict() for row in self.top_eligible_lows],
        }
        return body

    def as_log_envelope(self) -> dict[str, Any]:
        """Canonical logger diagnostics envelope (FP-P / FP-S)."""
        return {
            "diagnostic_log_version": self.diagnostic_log_version,
            "diagnostic_log": self.diagnostic_log_body(),
        }


def _compact(row: SwingDiagnostic, *, selected_shape: bool = False) -> CompactSwingRef:
    if selected_shape:
        return CompactSwingRef(
            swing_id=row.swing_id,
            price=row.price,
            lifecycle=row.lifecycle.value,
            eligible=row.eligible,
        )
    return CompactSwingRef(
        swing_id=row.swing_id,
        price=row.price,
        lifecycle=row.lifecycle.value,
        eligible=row.eligible,
        category=row.category.value,
        distance_ticks=row.distance_ticks,
        challenge_state=row.challenge_state,
    )


def _find_by_price(
    swings: tuple[SwingDiagnostic, ...], price: float | None
) -> SwingDiagnostic | None:
    if price is None:
        return None
    for row in swings:
        if row.price == price:
            return row
    return None


def derive_diagnostic_log(
    report: ObjectiveAuditReport | None,
    objective: ObjectiveSnapshot | None = None,
) -> DiagnosticLogProjection | None:
    """Derive projection P from runtime report R. Pure / one-way / deterministic.

    Never mutates ``report``. Never calls hierarchy.evaluate.
    """
    if report is None:
        return None

    eligible_highs = tuple(row for row in report.highs if row.eligible)
    eligible_lows = tuple(row for row in report.lows if row.eligible)
    challenged = sum(
        1
        for row in (*report.highs, *report.lows)
        if row.lifecycle is LifecycleState.CHALLENGED
    )

    selected_high_row = None
    selected_low_row = None
    if objective is not None:
        selected_high_row = _find_by_price(report.highs, objective.nearest_high_price)
        selected_low_row = _find_by_price(report.lows, objective.nearest_low_price)

    return DiagnosticLogProjection(
        diagnostic_log_version=DIAGNOSTIC_LOG_VERSION,
        source=DIAGNOSTIC_LOG_SOURCE,
        hierarchy_version=int(report.hierarchy_version),
        registry_size=int(report.registry_size),
        transition_count=int(report.transition_count),
        checkpoint_version=int(report.checkpoint_version),
        timestamp=float(report.timestamp),
        current_price=float(report.current_price),
        tick_size=float(report.tick_size),
        high_count=len(report.highs),
        low_count=len(report.lows),
        eligible_high_count=len(eligible_highs),
        eligible_low_count=len(eligible_lows),
        challenged_count=challenged,
        summary_line_count=len(report.summary_lines),
        selected_high=(
            None
            if selected_high_row is None
            else _compact(selected_high_row, selected_shape=True)
        ),
        selected_low=(
            None
            if selected_low_row is None
            else _compact(selected_low_row, selected_shape=True)
        ),
        summary_lines_head=tuple(report.summary_lines[:_SUMMARY_HEAD_MAX]),
        top_eligible_highs=tuple(
            _compact(row) for row in eligible_highs[:_TOP_K]
        ),
        top_eligible_lows=tuple(_compact(row) for row in eligible_lows[:_TOP_K]),
    )


def validate_ndjson_diagnostic_schema(payload: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
    """Validate Snapshot Logger diagnostics section against H-6.9.3 schema v1.

    Returns ``(ok, errors)``. Missing diagnostics section on empty frames is OK
    only when both envelope keys are absent. Partial / wrong version → FAIL.
    """
    errors: list[str] = []
    has_version = "diagnostic_log_version" in payload
    has_body = "diagnostic_log" in payload
    if not has_version and not has_body:
        return True, ()
    if not has_version:
        errors.append("missing diagnostic_log_version")
    else:
        version = payload["diagnostic_log_version"]
        if not isinstance(version, int) or isinstance(version, bool):
            errors.append("diagnostic_log_version must be uint")
        elif version != DIAGNOSTIC_LOG_VERSION:
            errors.append(
                f"diagnostic_log_version={version} unsupported (require {DIAGNOSTIC_LOG_VERSION})"
            )
    if not has_body:
        errors.append("missing diagnostic_log")
    else:
        body = payload["diagnostic_log"]
        if not isinstance(body, dict):
            errors.append("diagnostic_log must be object")
        else:
            for key in _REQUIRED_BODY_FIELDS:
                if key not in body:
                    errors.append(f"missing required field: {key}")
            if body.get("source") != DIAGNOSTIC_LOG_SOURCE:
                errors.append("source must be objective_audit_report")
            for key in _FORBIDDEN_DIAGNOSTIC_KEYS:
                if key in body:
                    errors.append(f"forbidden field in diagnostic_log: {key}")
            # Full SwingDiagnostic collections must not appear anywhere under body.
            for forbidden in ("highs", "lows"):
                if forbidden in body and isinstance(body[forbidden], (list, tuple)):
                    errors.append(f"forbidden full collection: {forbidden}")
    if "objective_diagnostics" in payload:
        errors.append("forbidden top-level objective_diagnostics (R) in logger payload")
    return (len(errors) == 0), tuple(errors)
