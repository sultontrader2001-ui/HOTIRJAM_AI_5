"""IDC Objective Engine page — read-only diagnostics (H-6.6.2).

Observes ValidatorFrame / ObjectiveSnapshot / attached diagnostics / existing
transition journal only. Never calls evaluate(), never mutates engines.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

from hotirjam_ai5.live_validator.models import ValidatorFrame
from hotirjam_ai5.objective_diagnostics.models import (
    LifecycleState,
    ObjectiveAuditReport,
    SwingDiagnostic,
)
from hotirjam_ai5.objective_diagnostics.persistent_hierarchy import StructuralTransition

_NA = "NOT AVAILABLE"
_RECENT_TRANSITIONS = 12

# Architecture-documented allowed exits (display only — not computed by engines).
_ALLOWED_NEXT: Mapping[LifecycleState, tuple[str, ...]] = {
    LifecycleState.NEW: ("ACTIVE",),
    LifecycleState.ACTIVE: ("CHALLENGED", "SUPERSEDED"),
    LifecycleState.CHALLENGED: ("ACTIVE", "CONFIRMED_BROKEN", "SUPERSEDED"),
    LifecycleState.CONFIRMED_BROKEN: ("ARCHIVED",),
    LifecycleState.SUPERSEDED: ("ARCHIVED",),
    LifecycleState.ARCHIVED: (),
}


def _fmt(value: float | None, *, digits: int = 2) -> str:
    if value is None:
        return _NA
    return f"{value:.{digits}f}"


def _fmt_time(timestamp: float | None) -> str:
    if timestamp is None:
        return _NA
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
    except (OverflowError, OSError, ValueError):
        return _fmt(timestamp, digits=0)


def _calculation_state(frame: ValidatorFrame) -> str:
    """Reuse existing completeness labels — no new market math."""
    obj = frame.objective
    if obj.is_complete:
        return "READY"
    if obj.has_high or obj.has_low:
        return "PARTIAL"
    return "NONE"


def _find_selected(
    swings: tuple[SwingDiagnostic, ...], price: float | None
) -> SwingDiagnostic | None:
    if price is None:
        return None
    for diagnostic in swings:
        if diagnostic.price == price:
            return diagnostic
    return None


def _lifecycle_label(diagnostic: SwingDiagnostic | None) -> str:
    if diagnostic is None:
        return _NA
    return diagnostic.lifecycle.value


def _allowed_next(diagnostic: SwingDiagnostic | None) -> str:
    if diagnostic is None:
        return _NA
    nxt = _ALLOWED_NEXT.get(diagnostic.lifecycle)
    if nxt is None:
        return _NA
    if not nxt:
        return "(terminal)"
    return ", ".join(nxt)


def _derive_health(
    frame: ValidatorFrame,
    report: ObjectiveAuditReport | None,
    *,
    feed_status: str | None,
) -> str:
    """Presentation health badge from existing fields only."""
    if feed_status == "STALE":
        return "CRITICAL"
    if frame.current_price is None and not frame.objective.has_high and not frame.objective.has_low:
        return "CRITICAL"
    if report is None:
        return "WARNING"
    if not frame.objective.is_complete:
        return "WARNING"
    return "HEALTHY"


def _certification_label(certifications: Mapping[str, str] | None) -> str:
    if not certifications:
        return _NA
    raw = certifications.get("objective")
    if raw is None or str(raw).strip() == "":
        return _NA
    return str(raw).upper().replace("_", " ").strip()


def _collect_warnings(
    frame: ValidatorFrame,
    report: ObjectiveAuditReport | None,
    transitions: Sequence[StructuralTransition] | None,
    *,
    feed_status: str | None,
) -> list[str]:
    warnings: list[str] = []
    if frame.current_price is None and not frame.objective.has_high and not frame.objective.has_low:
        warnings.append("Missing Snapshot")
    if report is None:
        warnings.append("Missing Diagnostics")
    if transitions is None:
        warnings.append("Transition Journal Not Exposed")
    elif report is not None and report.checkpoint_version <= 0 and report.hierarchy_version > 0:
        warnings.append("Stale Checkpoint")
    if feed_status == "STALE":
        warnings.append("Feed Interruption")
    return warnings


def _evidence_lines(
    high: SwingDiagnostic | None, low: SwingDiagnostic | None, report: ObjectiveAuditReport | None
) -> list[str]:
    if report is None and high is None and low is None:
        return [_NA]

    lines: list[str] = []
    if report is not None:
        lines.append(
            f"Hierarchy v{report.hierarchy_version}  "
            f"Registry {report.registry_size}  "
            f"Transitions {report.transition_count}  "
            f"Checkpoint v{report.checkpoint_version}"
        )
        if report.summary_lines:
            lines.extend(f"Summary {line}" for line in report.summary_lines[:6])

    def side_block(label: str, diagnostic: SwingDiagnostic | None) -> None:
        lines.append(f"{label}:")
        if diagnostic is None:
            lines.append(f"  {_NA}")
            return
        challenge = (
            " | ".join(diagnostic.challenge_evidence)
            if diagnostic.challenge_evidence
            else _NA
        )
        lines.extend(
            [
                f"  ID {diagnostic.swing_id}  Category {diagnostic.category.value}  "
                f"Eligible {'YES' if diagnostic.eligible else 'NO'}",
                f"  Persistence {_fmt(diagnostic.persistence)}  "
                f"Prominence {_fmt(diagnostic.prominence)}",
                f"  Challenge {diagnostic.challenge_state}  Evidence {challenge}",
            ]
        )

    side_block("High", high)
    side_block("Low", low)
    return lines if lines else [_NA]


def _reasons_lines(
    high: SwingDiagnostic | None, low: SwingDiagnostic | None, report: ObjectiveAuditReport | None
) -> list[str]:
    reasons: list[str] = []
    if report is not None:
        reasons.extend(report.summary_lines)
    for label, diagnostic in (("High", high), ("Low", low)):
        if diagnostic is None:
            continue
        if diagnostic.rejection_reasons:
            reasons.append(
                f"{label}: " + " | ".join(diagnostic.rejection_reasons)
            )
        if diagnostic.challenge_evidence:
            reasons.append(
                f"{label} challenge: " + " | ".join(diagnostic.challenge_evidence)
            )
        if diagnostic.transition_cause:
            reasons.append(f"{label} last cause: {diagnostic.transition_cause}")
    if not reasons:
        return [_NA]
    return reasons[:12]


def _journal_lines(transitions: Sequence[StructuralTransition] | None) -> list[str]:
    if transitions is None:
        return [_NA]
    if not transitions:
        return ["(empty)"]
    recent = list(transitions)[-_RECENT_TRANSITIONS:]
    lines = ["Timestamp                 Old → New                 Cause"]
    for item in reversed(recent):
        old = _NA
        new = _NA
        if item.old_state and "lifecycle" in item.old_state:
            old = str(item.old_state["lifecycle"])
        if item.new_state and "lifecycle" in item.new_state:
            new = str(item.new_state["lifecycle"])
        lines.append(
            f"{_fmt_time(item.timestamp)}  {old} → {new}  {item.cause}"
        )
    return lines


def render_objective_page(
    frame: ValidatorFrame | None,
    *,
    transitions: Sequence[StructuralTransition] | None = None,
    feed_status: str | None = None,
    certifications: Mapping[str, str] | None = None,
) -> str:
    """Render the IDC Objective Engine diagnostics page."""
    lines = [
        "==============================",
        "OBJECTIVE ENGINE",
        "----------------------------------------",
    ]

    if frame is None:
        lines.extend(
            [
                f"Status            {_NA}",
                f"Health            CRITICAL",
                f"Certification     {_certification_label(certifications)}",
                f"Last Evaluation   {_NA}",
                "----------------------------------------",
                "CURRENT SNAPSHOT",
                f"Current High      {_NA}",
                f"Current Low       {_NA}",
                f"Distance High     {_NA}",
                f"Distance Low      {_NA}",
                f"Calculation State {_NA}",
                "----------------------------------------",
                "LIFECYCLE",
                f"High Objective    {_NA}",
                f"Low Objective     {_NA}",
                f"Current Lifecycle {_NA}",
                f"Allowed Next States {_NA}",
                "----------------------------------------",
                "EVIDENCE",
                _NA,
                "----------------------------------------",
                "REASONS",
                _NA,
                "----------------------------------------",
                "TRANSITION JOURNAL",
                _NA,
                "----------------------------------------",
                "WARNINGS",
                "Missing Snapshot",
                "----------------------------------------",
                "",
                "Press Q to return",
                "",
            ]
        )
        return "\n".join(lines)

    report = frame.objective_diagnostics
    if report is not None and not isinstance(report, ObjectiveAuditReport):
        report = None

    projection = frame.diagnostic_log

    obj = frame.objective
    high = _find_selected(report.highs, obj.nearest_high_price) if report else None
    low = _find_selected(report.lows, obj.nearest_low_price) if report else None
    health = _derive_health(frame, report, feed_status=feed_status)
    status = feed_status if feed_status else _calculation_state(frame)

    high_life = _lifecycle_label(high)
    low_life = _lifecycle_label(low)
    if high is not None and low is not None:
        current_life = f"High={high_life} Low={low_life}"
    elif high is not None:
        current_life = f"High={high_life}"
    elif low is not None:
        current_life = f"Low={low_life}"
    else:
        current_life = _NA

    allowed_parts: list[str] = []
    if high is not None:
        allowed_parts.append(f"High: {_allowed_next(high)}")
    if low is not None:
        allowed_parts.append(f"Low: {_allowed_next(low)}")
    allowed = " | ".join(allowed_parts) if allowed_parts else _NA

    # Persistence states from ObjectiveSnapshot (engine output), separate from hierarchy lifecycle.
    high_persist = obj.high_state.value if obj.high_state is not None else _NA
    low_persist = obj.low_state.value if obj.low_state is not None else _NA

    # H-6.9.4: IDC summary from projection P (never evaluate).
    summary_lines: list[str] = [
        "SUMMARY (diagnostic_log)",
    ]
    if projection is None:
        summary_lines.append(_NA)
    else:
        summary_lines.extend(
            [
                f"Log Version       {projection.diagnostic_log_version}",
                f"Highs/Lows        {projection.high_count}/{projection.low_count}",
                f"Eligible H/L      {projection.eligible_high_count}/{projection.eligible_low_count}",
                f"Challenged        {projection.challenged_count}",
                f"Hierarchy Ver     {projection.hierarchy_version}",
                f"Transitions       {projection.transition_count}",
            ]
        )

    lines.extend(
        [
            f"Status            {status}",
            f"Health            {health}",
            f"Certification     {_certification_label(certifications)}",
            f"Last Evaluation   {_fmt_time(frame.timestamp)}",
            "----------------------------------------",
            *summary_lines,
            "----------------------------------------",
            "CURRENT SNAPSHOT",
            f"Current High      {_fmt(obj.nearest_high_price)}",
            f"Current Low       {_fmt(obj.nearest_low_price)}",
            f"Distance High     {_fmt(obj.nearest_high_distance_ticks, digits=1)}",
            f"Distance Low      {_fmt(obj.nearest_low_distance_ticks, digits=1)}",
            f"Calculation State {_calculation_state(frame)}",
            "----------------------------------------",
            "LIFECYCLE",
            f"High Objective    {high_life} (persist {high_persist})",
            f"Low Objective     {low_life} (persist {low_persist})",
            f"Current Lifecycle {current_life}",
            f"Allowed Next States {allowed}",
            "----------------------------------------",
            "DETAIL (objective_diagnostics)",
            "----------------------------------------",
            "EVIDENCE",
        ]
    )
    lines.extend(_evidence_lines(high, low, report))
    lines.append("----------------------------------------")
    lines.append("REASONS")
    lines.extend(_reasons_lines(high, low, report))
    lines.append("----------------------------------------")
    lines.append("TRANSITION JOURNAL")
    lines.extend(_journal_lines(transitions))
    lines.append("----------------------------------------")
    lines.append("WARNINGS")
    warnings = _collect_warnings(frame, report, transitions, feed_status=feed_status)
    if warnings:
        lines.extend(warnings)
    else:
        lines.append("(none)")
    lines.extend(
        [
            "----------------------------------------",
            "",
            "Press Q to return",
            "",
        ]
    )
    return "\n".join(lines)
