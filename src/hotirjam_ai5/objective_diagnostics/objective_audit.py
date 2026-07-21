"""Objective audit — assemble the shared structural landscape report.

Read-only and deterministic. Objective Engine V2 consumes its classifications;
Developer View renders the same report as selection evidence.
"""

from __future__ import annotations

from hotirjam_ai5.objective_diagnostics.candidate_report import (
    evaluate_eligibility,
    sort_candidates,
)
from hotirjam_ai5.objective_diagnostics.hierarchy_builder import build_hierarchy
from hotirjam_ai5.objective_diagnostics.models import (
    ObjectiveAuditReport,
    ObjectiveDiagnosticsInputs,
    SwingDiagnostic,
    SwingSide,
)
from hotirjam_ai5.objective_diagnostics.significance_diagnostics import (
    classify_category,
    compute_persistence,
    compute_prominence_ticks,
    resolve_lifecycle,
)


def audit_objectives(inputs: ObjectiveDiagnosticsInputs) -> ObjectiveAuditReport:
    """Build ranked diagnostic reports for all confirmed highs and lows."""
    if inputs.tick_size <= 0.0:
        empty = ObjectiveAuditReport(
            timestamp=inputs.timestamp,
            current_price=inputs.current_price,
            tick_size=inputs.tick_size,
            highs=(),
            lows=(),
            summary_lines=("Invalid tick size — diagnostics skipped",),
        )
        return empty

    nodes = build_hierarchy(inputs.confirmed_highs, inputs.confirmed_lows)
    diagnostics: list[SwingDiagnostic] = []

    for node in nodes:
        prominence = compute_prominence_ticks(node, nodes, tick_size=inputs.tick_size)
        persistence = compute_persistence(node, prominence)
        category = classify_category(
            depth=node.depth,
            prominence_ticks=prominence,
            persistence=persistence,
        )
        lifecycle = resolve_lifecycle(
            node,
            nodes,
            current_price=inputs.current_price,
            tick_size=inputs.tick_size,
            session_high=inputs.session_high,
            session_low=inputs.session_low,
        )
        distance = abs(node.swing.price - inputs.current_price) / inputs.tick_size
        eligible, reasons = evaluate_eligibility(
            side=node.side,
            price=node.swing.price,
            current_price=inputs.current_price,
            lifecycle=lifecycle,
            category=category,
            depth=node.depth,
            prominence=prominence,
            parent_swing_id=node.parent_swing_id,
        )
        diagnostics.append(
            SwingDiagnostic(
                swing_id=node.swing_id,
                side=node.side,
                price=node.swing.price,
                confirmed_at=node.swing.confirmed_at,
                distance_ticks=distance,
                current_strength=node.swing.strength,
                parent_swing_id=node.parent_swing_id,
                hierarchy_depth=node.depth,
                persistence=persistence,
                prominence=prominence,
                lifecycle=lifecycle,
                category=category,
                eligible=eligible,
                rejection_reasons=reasons,
            )
        )

    highs = sort_candidates([d for d in diagnostics if d.side is SwingSide.HIGH])
    lows = sort_candidates([d for d in diagnostics if d.side is SwingSide.LOW])
    summary = tuple(_format_report(highs, lows))
    return ObjectiveAuditReport(
        timestamp=inputs.timestamp,
        current_price=inputs.current_price,
        tick_size=inputs.tick_size,
        highs=tuple(highs),
        lows=tuple(lows),
        summary_lines=summary,
    )


def format_audit_report(report: ObjectiveAuditReport) -> str:
    """Plain-text ranked landscape for logging / display."""
    return "\n".join(report.summary_lines)


def _format_report(
    highs: list[SwingDiagnostic],
    lows: list[SwingDiagnostic],
) -> list[str]:
    lines: list[str] = [
        "OBJECTIVE STRUCTURAL DIAGNOSTICS (read-only)",
        "===========================================",
        "",
        "HIGHS",
    ]
    if not highs:
        lines.append("(none)")
    else:
        for d in highs:
            lines.extend(_format_swing(d))
    lines.extend(["", "LOWS"])
    if not lows:
        lines.append("(none)")
    else:
        for d in lows:
            lines.extend(_format_swing(d))
    return lines


def _format_swing(d: SwingDiagnostic) -> list[str]:
    lines = [
        f"ID {d.swing_id}",
        f"{d.category.value}",
        f"{d.lifecycle.value}",
    ]
    if d.eligible:
        lines.append("Eligible YES")
    else:
        lines.append("Eligible NO")
        lines.append("Rejected")
        for reason in d.rejection_reasons:
            lines.append(f"Reason {reason}")
    lines.append(
        f"Price {d.price:.2f}  Dist {d.distance_ticks:.1f}t  "
        f"Str {d.current_strength:.1f}  Parent {d.parent_swing_id}  "
        f"Depth {d.hierarchy_depth}  Persist {d.persistence:.1f}  "
        f"Prom {d.prominence:.1f}t"
    )
    lines.append("")
    return lines
