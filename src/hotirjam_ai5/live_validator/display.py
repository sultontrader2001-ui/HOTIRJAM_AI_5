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
        "Low:",
        f"  Price     {_fmt(obj.nearest_low_price)}",
        f"  Distance  {_fmt(obj.nearest_low_distance_ticks)}",
        f"  Strength  {_fmt(obj.nearest_low_strength)}",
    ]
    lines.extend(_render_structural_diagnostics(frame.objective_diagnostics))
    lines.extend(
        [
            "==============================",
            "INITIATIVE",
            "==============================",
            f"Side {ini.initiative_side.value}  score={_fmt(ini.initiative_score)}  "
            f"state={ini.state.value}  conf={_fmt(ini.confidence)}",
            f"Impulse/Mom/Cndl {_fmt(ini.impulse_score)} / {_fmt(ini.momentum_score)} / "
            f"{_fmt(ini.candle_strength_score)}",
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

    def side_block(title: str, swings: tuple[SwingDiagnostic, ...]) -> list[str]:
        block = [title]
        if not swings:
            block.append("(none)")
            block.append("--------------------------------")
            return block
        for d in swings:
            block.extend(
                [
                    f"ID              {d.swing_id}",
                    f"Price           {_fmt(d.price)}",
                    f"Category        {d.category.value}",
                    f"Lifecycle       {d.lifecycle.value}",
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
    )
