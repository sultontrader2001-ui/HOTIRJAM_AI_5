"""Terminal display for Live Validator (observation only).

Presentation layer only. Does not alter engine calculations or scores.
Default view is the Live Certification Dashboard; D toggles Developer View.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone

from hotirjam_ai5.live_validator.certification_dashboard import (
    AuditLog,
    MarketTelemetry,
    render_certification_dashboard,
)
from hotirjam_ai5.live_validator.models import ValidatorFrame


def _fmt(value: float | None, *, digits: int = 2) -> str:
    if value is None:
        return "--"
    return f"{value:.{digits}f}"


def _fmt_time(timestamp: float) -> str:
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%H:%M:%S UTC")
    except (OverflowError, OSError, ValueError):
        return _fmt(timestamp, digits=0)


def _feed_status_label(feed_status: str | None, frame: ValidatorFrame) -> str:
    if feed_status:
        return feed_status
    return "LIVE" if frame.current_price is not None else "WAITING"


def render_developer_view(
    frame: ValidatorFrame,
    *,
    feed_status: str | None = None,
) -> str:
    """Optional developer overlay — raw scores still available, not default."""
    obj = frame.objective
    ini = frame.initiative
    resp = frame.response
    cont = frame.continuation
    brk = frame.break_capability

    def reasons(rs: tuple[str, ...]) -> str:
        if not rs:
            return "--"
        return " | ".join(rs[:4])

    lines = [
        "==============================",
        "HOTIRJAM AI 5",
        "LIVE ANALYSIS — DEVELOPER VIEW",
        "==============================",
        f"Symbol            {frame.symbol}",
        f"Current Price     {_fmt(frame.current_price)}",
        f"Current Time      {_fmt_time(frame.timestamp)}",
        f"Feed Status       {_feed_status_label(feed_status, frame)}",
        f"Candles / Swings  {frame.candle_count}  H:{frame.swing_high_count} L:{frame.swing_low_count}",
        "==============================",
        "CURRENT OBJECTIVE",
        "-----------------",
        "High:",
        f"  Price     {_fmt(obj.nearest_high_price)}",
        f"  Distance  {_fmt(obj.nearest_high_distance_ticks)}",
        f"  Strength  {_fmt(obj.nearest_high_strength)}",
        f"  Objective State {obj.high_state.value if obj.high_state is not None else 'NOT AVAILABLE'}",
        "Low:",
        f"  Price     {_fmt(obj.nearest_low_price)}",
        f"  Distance  {_fmt(obj.nearest_low_distance_ticks)}",
        f"  Strength  {_fmt(obj.nearest_low_strength)}",
        f"  Objective State {obj.low_state.value if obj.low_state is not None else 'NOT AVAILABLE'}",
    ]
    lines.extend(_render_objective_diagnostics(frame))
    lines.extend(_render_structural_diagnostics(frame.objective_diagnostics))
    lines.extend(
        [
            "==============================",
            "INITIATIVE",
            "==============================",
            f"Initiative State {ini.initiative_state.value}",
            f"Dominant Side    {ini.dominant_side.value}",
            f"Buyer Initiative {_fmt(ini.buyer_initiative)}",
            f"Seller Initiative {_fmt(ini.seller_initiative)}",
            f"Confidence       {_fmt(ini.confidence)}",
            f"Evidence Summary {' | '.join(ini.evidence.summary_lines())}",
            f"Reasons {reasons(ini.reasons)}",
            "==============================",
            "RESPONSE",
            "==============================",
            f"Side {resp.response_side.value}  strength={_fmt(resp.response_strength)}  "
            f"state={resp.response_state.value}  preserved={resp.initiative_preserved}  "
            f"conf={_fmt(resp.confidence)}",
            f"Reasons {reasons(resp.reasons)}",
            "==============================",
            "CONTINUATION",
            "==============================",
            f"Side {cont.continuation_side.value}  score={_fmt(cont.continuation_score)}  "
            f"state={cont.state.value}",
            f"Pressure/Decay {_fmt(cont.pressure_score)} / {_fmt(cont.momentum_decay)}  "
            f"conf={_fmt(cont.confidence)}",
            f"Reasons {reasons(cont.reasons)}",
            "==============================",
            "BREAK CAPABILITY",
            "==============================",
            f"Target {brk.target_side.value} → {brk.target_type.value}",
            f"Break Prob {_fmt(brk.break_probability)}  state={brk.state.value}",
            f"Pressure/Resist {_fmt(brk.pressure_score)} / {_fmt(brk.resistance_score)}  "
            f"conf={_fmt(brk.confidence)}",
            f"Reasons {reasons(brk.reasons)}",
            "==============================",
            "Decision Engine   DISABLED",
            "Execution Engine  DISABLED",
            "Observation Mode  No Orders",
            "",
            "Press D — Certification Dashboard",
        ]
    )
    return "\n".join(lines)


def _render_objective_diagnostics(frame: ValidatorFrame) -> list[str]:
    """Explain WHY the current objective was selected. Read-only over the
    attached ObjectiveAuditReport; never invents values."""
    from hotirjam_ai5.objective_diagnostics import ObjectiveAuditReport, SwingDiagnostic

    header = [
        "====================================",
        "OBJECTIVE DIAGNOSTICS",
        "------------------------------------",
    ]
    report = frame.objective_diagnostics
    if report is None or not isinstance(report, ObjectiveAuditReport):
        return [*header, "NOT AVAILABLE", "===================================="]

    def find_selected(
        swings: tuple[SwingDiagnostic, ...], price: float | None
    ) -> SwingDiagnostic | None:
        if price is None:
            return None
        for d in swings:
            if d.price == price:
                return d
        return None

    def detail_block(title: str, d: SwingDiagnostic | None) -> list[str]:
        block = [title]
        if d is None:
            block.append("NOT AVAILABLE")
            block.append("------------------------------------")
            return block
        reasons = " | ".join(d.rejection_reasons) if d.rejection_reasons else "--"
        challenge_evidence = (
            " | ".join(d.challenge_evidence) if d.challenge_evidence else "--"
        )
        block.extend(
            [
                f"ID               {d.swing_id}",
                f"Category         {d.category.value}",
                f"Eligible         {'YES' if d.eligible else 'NO'}",
                f"Lifecycle        {d.lifecycle.value}",
                f"Challenge State  {d.challenge_state}",
                f"Challenge Evidence {challenge_evidence}",
                f"Transition Cause {d.transition_cause or '--'}",
                f"Transition Time  {d.transition_time if d.transition_time is not None else '--'}",
                f"Parent ID        {d.parent_swing_id if d.parent_swing_id is not None else '--'}",
                f"Hierarchy Depth  {d.hierarchy_depth}",
                f"Persistence      {_fmt(d.persistence)}",
                f"Prominence       {_fmt(d.prominence)}",
                f"Rejection Reason {reasons}",
                "------------------------------------",
            ]
        )
        return block

    def next_eligible(swings: tuple[SwingDiagnostic, ...]) -> SwingDiagnostic | None:
        eligible = [d for d in swings if d.eligible]
        if not eligible:
            return None
        return min(eligible, key=lambda d: (d.distance_ticks, d.swing_id))

    def eligible_block(title: str, d: SwingDiagnostic | None) -> list[str]:
        block = [title]
        if d is None:
            block.append("NOT AVAILABLE")
            return block
        reasons = " | ".join(d.rejection_reasons) if d.rejection_reasons else "--"
        block.extend(
            [
                f"ID               {d.swing_id}",
                f"Category         {d.category.value}",
                f"Distance         {_fmt(d.distance_ticks, digits=1)}",
                f"Eligible         {'YES' if d.eligible else 'NO'}",
                f"Reason           {reasons}",
            ]
        )
        return block

    obj = frame.objective
    lines = list(header)
    lines.extend(detail_block("CURRENT HIGH", find_selected(report.highs, obj.nearest_high_price)))
    lines.extend(detail_block("CURRENT LOW", find_selected(report.lows, obj.nearest_low_price)))
    lines.append("NEXT ELIGIBLE STRUCTURAL OBJECTIVE")
    lines.extend(eligible_block("High", next_eligible(report.highs)))
    lines.extend(eligible_block("Low", next_eligible(report.lows)))
    lines.append("====================================")
    return lines


def _render_structural_diagnostics(report: object | None) -> list[str]:
    """Format attached ObjectiveAuditReport for Developer View only."""
    from hotirjam_ai5.objective_diagnostics import (
        CandidateCategory,
        ObjectiveAuditReport,
        SwingDiagnostic,
    )

    lines = [
        "====================================",
        "STRUCTURAL OBJECTIVE DIAGNOSTICS",
    ]
    if report is None or not isinstance(report, ObjectiveAuditReport):
        lines.append("No diagnostics available.")
        lines.append("====================================")
        return lines
    lines.extend(
        [
            f"Hierarchy Version {report.hierarchy_version}",
            f"Registry Size     {report.registry_size}",
            f"Transition Count  {report.transition_count}",
            f"Checkpoint Version {report.checkpoint_version}",
            "--------------------------------",
        ]
    )

    def side_block(title: str, swings: tuple[SwingDiagnostic, ...]) -> list[str]:
        block = [title]
        if not swings:
            block.append("(none)")
            block.append("--------------------------------")
            return block
        for d in swings:
            challenge_evidence = (
                " | ".join(d.challenge_evidence) if d.challenge_evidence else "--"
            )
            block.extend(
                [
                    f"ID              {d.swing_id}",
                    f"Price           {_fmt(d.price)}",
                    f"Category        {d.category.value}",
                    f"Lifecycle       {d.lifecycle.value}",
                    f"Challenge State {d.challenge_state}",
                    f"Challenge Evidence {challenge_evidence}",
                    f"Transition Cause {d.transition_cause or '--'}",
                    f"Transition Time {d.transition_time if d.transition_time is not None else '--'}",
                    f"Eligible        {'YES' if d.eligible else 'NO'}",
                    f"Parent ID       {d.parent_swing_id if d.parent_swing_id is not None else '--'}",
                    f"Hierarchy Depth {d.hierarchy_depth}",
                    f"Persistence     {_fmt(d.persistence)}",
                    f"Prominence      {_fmt(d.prominence)}",
                ]
            )
            if d.rejection_reasons:
                block.append("Rejection Reasons")
                for reason in d.rejection_reasons:
                    block.append(f"  - {reason}")
            else:
                block.append("Rejection Reasons --")
            block.append("")
        block.append("--------------------------------")
        return block

    lines.extend(side_block("HIGHS", report.highs))
    lines.extend(side_block("LOWS", report.lows))

    all_swings = (*report.highs, *report.lows)
    micro = sum(1 for d in all_swings if d.category is CandidateCategory.MICRO)
    minor = sum(1 for d in all_swings if d.category is CandidateCategory.MINOR)
    major = sum(1 for d in all_swings if d.category is CandidateCategory.MAJOR)
    eligible_highs = sum(1 for d in report.highs if d.eligible)
    eligible_lows = sum(1 for d in report.lows if d.eligible)
    lines.extend(
        [
            "Summary",
            f"Total Swings    {len(all_swings)}",
            f"Micro           {micro}",
            f"Minor           {minor}",
            f"Major           {major}",
            f"Eligible Highs  {eligible_highs}",
            f"Eligible Lows   {eligible_lows}",
            "====================================",
        ]
    )
    return lines


def render_validator_frame(
    frame: ValidatorFrame,
    *,
    developer_mode: bool = False,
    feed_status: str | None = None,
    market: MarketTelemetry | None = None,
    uptime_seconds: float | None = None,
    audit: AuditLog | None = None,
    certifications: Mapping[str, str] | None = None,
    terminal_width: int | None = None,
    use_color: bool = False,
) -> str:
    """Render observation frame. Default is the Live Certification Dashboard."""
    if developer_mode:
        return render_developer_view(frame, feed_status=feed_status)
    return render_certification_dashboard(
        frame,
        feed_status=_feed_status_label(feed_status, frame),
        market=market,
        uptime_seconds=uptime_seconds,
        audit=audit,
        certifications=certifications,
        terminal_width=terminal_width,
        use_color=use_color,
    )
