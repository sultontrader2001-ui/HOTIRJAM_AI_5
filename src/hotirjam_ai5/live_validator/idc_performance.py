"""IDC Performance page — render existing LoopTimingSnapshot (H-6.6.5).

Read-only presentation of instrumentation already collected by H-6.6.4.
Never measures, never restarts timers, never calls evaluate().
"""

from __future__ import annotations

from datetime import datetime, timezone

from hotirjam_ai5.live_validator.loop_timing import (
    LoopTimingSnapshot,
    TimingSeverity,
)

_NA = "NOT AVAILABLE"

_STAGE_LABELS: tuple[tuple[str, str], ...] = (
    ("loop", "Loop Time"),
    ("poll", "poll_once()"),
    ("keyboard", "Keyboard Poll"),
    ("render", "render_once()"),
    ("initiative_checkpoint", "Initiative Checkpoint"),
    ("hierarchy_checkpoint", "Hierarchy Checkpoint"),
    ("checkpoint", "Combined Checkpoint"),
    ("logging", "Snapshot Logger"),
    ("sleep", "Sleep Time"),
)


def _fmt_ms(value: float | None) -> str:
    if value is None:
        return _NA
    return f"{value:.2f} ms"


def _fmt_sample(timing: LoopTimingSnapshot) -> str:
    """Show existing perf_counter bounds from the snapshot — no invented wall clock."""
    return f"perf {timing.start_time:.6f} → {timing.end_time:.6f}"


def _ms_for_stage(snap: LoopTimingSnapshot, stage: str) -> float:
    return {
        "loop": snap.loop_ms,
        "poll": snap.poll_ms,
        "keyboard": snap.keyboard_ms,
        "render": snap.render_ms,
        "sleep": snap.sleep_ms,
        "checkpoint": snap.checkpoint_ms,
        "initiative_checkpoint": snap.initiative_checkpoint_ms,
        "hierarchy_checkpoint": snap.hierarchy_checkpoint_ms,
        "logging": snap.logging_ms,
    }[stage]


def _health_from_snapshot(snap: LoopTimingSnapshot) -> str:
    """Map existing severities only — no new thresholds."""
    severities = (
        snap.loop_severity,
        snap.poll_severity,
        snap.keyboard_severity,
        snap.render_severity,
        snap.sleep_severity,
        snap.checkpoint_severity,
        snap.initiative_checkpoint_severity,
        snap.hierarchy_checkpoint_severity,
        snap.logging_severity,
    )
    if TimingSeverity.CRITICAL in severities:
        return TimingSeverity.CRITICAL.value
    if TimingSeverity.SLOW in severities:
        return TimingSeverity.SLOW.value
    return TimingSeverity.OK.value


def _longest_stage(snap: LoopTimingSnapshot) -> tuple[str, float]:
    best_label = "Loop Time"
    best_ms = snap.loop_ms
    for stage, label in _STAGE_LABELS:
        ms = _ms_for_stage(snap, stage)
        if ms > best_ms:
            best_label = label
            best_ms = ms
    return best_label, best_ms


def _warnings(snap: LoopTimingSnapshot) -> list[str]:
    """Only surface SLOW / CRITICAL already present on the snapshot."""
    warnings: list[str] = []
    for stage, label in _STAGE_LABELS:
        severity = snap.stage_severity(stage)
        if severity is TimingSeverity.SLOW or severity is TimingSeverity.CRITICAL:
            warnings.append(
                f"{severity.value}  {label}  {_fmt_ms(_ms_for_stage(snap, stage))}"
            )
    return warnings


def render_performance_page(
    timing: LoopTimingSnapshot | None,
    *,
    feed_status: str | None = None,
) -> str:
    """Render the IDC Performance diagnostics page from existing timing only."""
    lines = [
        "==============================",
        "PERFORMANCE",
        "----------------------------------------",
    ]

    if timing is None:
        lines.extend(
            [
                f"Status            {feed_status if feed_status else _NA}",
                f"Health            {_NA}",
                f"Last Sample       {_NA}",
                "----------------------------------------",
                "MAIN LOOP",
                f"Loop Time         {_NA}",
                f"Status            {_NA}",
                "----------------------------------------",
                "PIPELINE",
                f"poll_once()       {_NA}",
                f"Status            {_NA}",
                "----------------------------------------",
                "KEYBOARD",
                f"Keyboard Poll     {_NA}",
                f"Status            {_NA}",
                "----------------------------------------",
                "RENDER",
                f"render_once()     {_NA}",
                f"Status            {_NA}",
                "----------------------------------------",
                "CHECKPOINTS",
                f"Initiative Checkpoint {_NA}",
                f"Hierarchy Checkpoint  {_NA}",
                f"Combined Checkpoint   {_NA}",
                f"Status            {_NA}",
                "----------------------------------------",
                "LOGGING",
                f"Snapshot Logger   {_NA}",
                f"Status            {_NA}",
                "----------------------------------------",
                "SLEEP",
                f"Sleep Time        {_NA}",
                "----------------------------------------",
                "SUMMARY",
                f"Longest Stage     {_NA}",
                f"Longest Duration  {_NA}",
                f"Overall Status    {_NA}",
                "----------------------------------------",
                "WARNINGS",
                "(none)",
                "----------------------------------------",
                "",
                "Press Q to return",
                "",
            ]
        )
        return "\n".join(lines)

    health = _health_from_snapshot(timing)
    status = feed_status if feed_status else health
    longest_label, longest_ms = _longest_stage(timing)

    lines.extend(
        [
            f"Status            {status}",
            f"Health            {health}",
            f"Last Sample       {_fmt_sample(timing)}",
            "----------------------------------------",
            "MAIN LOOP",
            f"Loop Time         {_fmt_ms(timing.loop_ms)}",
            f"Status            {timing.loop_severity.value}",
            "----------------------------------------",
            "PIPELINE",
            f"poll_once()       {_fmt_ms(timing.poll_ms)}",
            f"Status            {timing.poll_severity.value}",
            "----------------------------------------",
            "KEYBOARD",
            f"Keyboard Poll     {_fmt_ms(timing.keyboard_ms)}",
            f"Status            {timing.keyboard_severity.value}",
            "----------------------------------------",
            "RENDER",
            f"render_once()     {_fmt_ms(timing.render_ms)}",
            f"Status            {timing.render_severity.value}",
            "----------------------------------------",
            "CHECKPOINTS",
            f"Initiative Checkpoint {_fmt_ms(timing.initiative_checkpoint_ms)}",
            f"Hierarchy Checkpoint  {_fmt_ms(timing.hierarchy_checkpoint_ms)}",
            f"Combined Checkpoint   {_fmt_ms(timing.checkpoint_ms)}",
            f"Status            {timing.checkpoint_severity.value}",
            "----------------------------------------",
            "LOGGING",
            f"Snapshot Logger   {_fmt_ms(timing.logging_ms)}",
            f"Status            {timing.logging_severity.value}",
            "----------------------------------------",
            "SLEEP",
            f"Sleep Time        {_fmt_ms(timing.sleep_ms)}",
            "----------------------------------------",
            "SUMMARY",
            f"Longest Stage     {longest_label}",
            f"Longest Duration  {_fmt_ms(longest_ms)}",
            f"Overall Status    {health}",
            "----------------------------------------",
            "WARNINGS",
        ]
    )
    warnings = _warnings(timing)
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
