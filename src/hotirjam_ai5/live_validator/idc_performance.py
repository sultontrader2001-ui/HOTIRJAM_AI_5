"""IDC Performance page — render LoopTimingSnapshot (+ H-6.6.6 breakdowns).

Read-only presentation of instrumentation. Never measures, never restarts
timers, never calls evaluate().
"""

from __future__ import annotations

from hotirjam_ai5.live_data.ingress_poll_snapshot import IngressPollSnapshot
from hotirjam_ai5.live_validator.loop_timing import (
    CheckpointExclusiveBreakdown,
    HierarchyFootprint,
    LoggingExclusiveBreakdown,
    LoggingFootprint,
    LoopTimingSnapshot,
    StageBreakdown,
    TickRetentionBreakdown,
    TimingSeverity,
)
from hotirjam_ai5.retention import RetentionSnapshot

_NA = "NOT AVAILABLE"
_N_A = "NOT APPLICABLE"

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


def _fmt_stage_ms(value: float | None, *, available: bool) -> str:
    """Format a breakdown stage: missing sample, N/A stage, or milliseconds."""
    if not available:
        return _NA
    if value is None:
        return _N_A
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


def _breakdown_lines(
    title: str,
    total_ms: float,
    breakdown: StageBreakdown | None,
    *,
    sample_available: bool,
) -> list[str]:
    """Legacy Collect/Build/... lines (kept for Hierarchy internal sample)."""
    available = sample_available and breakdown is not None
    return [
        title,
        f"  Total........... {_fmt_ms(total_ms) if sample_available else _NA}",
        f"  Collect......... {_fmt_stage_ms(None if breakdown is None else breakdown.collect_ms, available=available)}",
        f"  Build........... {_fmt_stage_ms(None if breakdown is None else breakdown.build_ms, available=available)}",
        f"  Serialize....... {_fmt_stage_ms(None if breakdown is None else breakdown.serialize_ms, available=available)}",
        f"  Write........... {_fmt_stage_ms(None if breakdown is None else breakdown.write_ms, available=available)}",
        f"  Flush........... {_fmt_stage_ms(None if breakdown is None else breakdown.flush_ms, available=available)}",
    ]


def _logging_exclusive_lines(
    total_ms: float,
    breakdown: LoggingExclusiveBreakdown | None,
    *,
    sample_available: bool,
) -> list[str]:
    """H-6.7.1 exclusive Snapshot Logger stages."""
    available = sample_available and breakdown is not None
    return [
        "Snapshot Logger",
        f"  Total........... {_fmt_ms(total_ms) if sample_available else _NA}",
        f"  Build........... {_fmt_stage_ms(None if breakdown is None else breakdown.build_ms, available=available)}",
        f"  Serialize....... {_fmt_stage_ms(None if breakdown is None else breakdown.serialize_ms, available=available)}",
        f"  Write........... {_fmt_stage_ms(None if breakdown is None else breakdown.write_ms, available=available)}",
        f"  Flush........... {_fmt_stage_ms(None if breakdown is None else breakdown.flush_ms, available=available)}",
        f"  Rotate.......... {_fmt_stage_ms(None if breakdown is None else breakdown.rotate_ms, available=available)}",
        f"  Reopen.......... {_fmt_stage_ms(None if breakdown is None else breakdown.reopen_ms, available=available)}",
    ]


def _checkpoint_exclusive_lines(
    total_ms: float,
    breakdown: CheckpointExclusiveBreakdown | None,
    *,
    sample_available: bool,
) -> list[str]:
    """H-6.7.1 exclusive Combined Checkpoint stages."""
    available = sample_available and breakdown is not None
    return [
        "Combined Checkpoint",
        f"  Total........... {_fmt_ms(total_ms) if sample_available else _NA}",
        f"  Assemble........ {_fmt_stage_ms(None if breakdown is None else breakdown.assemble_ms, available=available)}",
        f"  Serialize....... {_fmt_stage_ms(None if breakdown is None else breakdown.serialize_ms, available=available)}",
        f"  Write........... {_fmt_stage_ms(None if breakdown is None else breakdown.write_ms, available=available)}",
        f"  Flush........... {_fmt_stage_ms(None if breakdown is None else breakdown.flush_ms, available=available)}",
        f"  fsync........... {_fmt_stage_ms(None if breakdown is None else breakdown.fsync_ms, available=available)}",
        f"  os.replace...... {_fmt_stage_ms(None if breakdown is None else breakdown.os_replace_ms, available=available)}",
    ]


def _tick_retention_lines(
    breakdown: TickRetentionBreakdown | None,
    *,
    sample_available: bool,
) -> list[str]:
    """H-6.7.1 exclusive Tick Retention stages."""
    available = sample_available and breakdown is not None
    return [
        "Tick Retention",
        f"  Total........... {_fmt_stage_ms(None if breakdown is None else breakdown.total_ms, available=available)}",
        f"  stat............ {_fmt_stage_ms(None if breakdown is None else breakdown.stat_ms, available=available)}",
        f"  read retained... {_fmt_stage_ms(None if breakdown is None else breakdown.read_ms, available=available)}",
        f"  Write........... {_fmt_stage_ms(None if breakdown is None else breakdown.write_ms, available=available)}",
        f"  fsync........... {_fmt_stage_ms(None if breakdown is None else breakdown.fsync_ms, available=available)}",
        f"  replace......... {_fmt_stage_ms(None if breakdown is None else breakdown.replace_ms, available=available)}",
    ]


def _fmt_bytes(value: int | None, *, available: bool) -> str:
    if not available or value is None:
        return _NA
    return f"{value} bytes"


def _fmt_mb(value_bytes: int | None, *, available: bool) -> str:
    if not available or value_bytes is None:
        return _NA
    return f"{value_bytes / (1024.0 * 1024.0):.2f} MB"


def _fmt_count(value: int | None, *, available: bool) -> str:
    if not available or value is None:
        return _NA
    return str(value)


def _hierarchy_footprint_lines(
    footprint: HierarchyFootprint | None, *, sample_available: bool
) -> list[str]:
    available = sample_available and footprint is not None
    lines = [
        "Hierarchy Footprint",
        f"  Registry........ {_fmt_count(None if footprint is None else footprint.registry_entries, available=available)}",
        f"  Hierarchy Nodes. {_fmt_count(None if footprint is None else footprint.hierarchy_nodes, available=available)}",
        f"  Journal......... {_fmt_count(None if footprint is None else footprint.journal_entries, available=available)}",
        f"  Snapshot Objs... {_fmt_count(None if footprint is None else footprint.snapshot_object_count, available=available)}",
        f"  JSON Size....... {_fmt_bytes(None if footprint is None else footprint.json_size_bytes, available=available)}",
        f"  JSON Size MB.... {_fmt_mb(None if footprint is None else footprint.json_size_bytes, available=available)}",
        f"  Largest Section. {_NA if not available or footprint is None or footprint.largest_section is None else footprint.largest_section}",
        f"  Largest Size.... {_fmt_bytes(None if footprint is None else footprint.largest_section_bytes, available=available)}",
    ]
    if available and footprint is not None and footprint.section_sizes:
        lines.append("  Top-level Sections")
        for section in footprint.section_sizes[:8]:
            lines.append(
                f"    {section.name}.... {_fmt_bytes(section.size_bytes, available=True)}"
            )
    return lines


def _logging_footprint_lines(
    footprint: LoggingFootprint | None, *, sample_available: bool
) -> list[str]:
    available = sample_available and footprint is not None
    lines = [
        "Snapshot Logger Footprint",
        f"  Frame Objects... {_fmt_count(None if footprint is None else footprint.frame_object_count, available=available)}",
        f"  JSON Size....... {_fmt_bytes(None if footprint is None else footprint.json_size_bytes, available=available)}",
        f"  JSON Size MB.... {_fmt_mb(None if footprint is None else footprint.json_size_bytes, available=available)}",
        f"  Largest Section. {_NA if not available or footprint is None or footprint.largest_section is None else footprint.largest_section}",
        f"  Largest Size.... {_fmt_bytes(None if footprint is None else footprint.largest_section_bytes, available=available)}",
    ]
    if available and footprint is not None:
        sections = ", ".join(footprint.top_level_sections) if footprint.top_level_sections else _NA
        lines.append(f"  Top-level Keys.. {sections}")
        if footprint.section_sizes:
            lines.append("  Top-level Sections")
            for section in footprint.section_sizes[:8]:
                lines.append(
                    f"    {section.name}.... {_fmt_bytes(section.size_bytes, available=True)}"
                )
    return lines


def _ingress_poll_lines(snapshot: IngressPollSnapshot | None) -> list[str]:
    """TEMPORARY Feed WAITING triage block (Gate A vs Gate B)."""
    lines = [
        "FEED INGRESS (TEMPORARY)",
        "----------------------------------------",
    ]
    if snapshot is None:
        lines.extend(
            [
                f"Gate              {_NA}",
                f"tail_return       {_NA}",
                f"tail_lines        {_NA}",
                f"accepted_count    {_NA}",
                f"skipped_count     {_NA}",
                f"file_offset       {_NA}",
                f"file_size         {_NA}",
            ]
        )
        return lines
    offset = _NA if snapshot.file_offset is None else str(snapshot.file_offset)
    size = _NA if snapshot.file_size is None else str(snapshot.file_size)
    lines.extend(
        [
            f"Gate              {snapshot.gate}",
            f"tail_return       {snapshot.tail_return or _NA}",
            f"tail_lines        {snapshot.tail_lines}",
            f"accepted_count    {snapshot.accepted_count}",
            f"skipped_count     {snapshot.skipped_count}",
            f"accepted_delta    {snapshot.accepted_delta}",
            f"skipped_delta     {snapshot.skipped_delta}",
            f"file_offset       {offset}",
            f"file_size         {size}",
        ]
    )
    return lines


def _fmt_bytes_size(value: int | None) -> str:
    if value is None:
        return _NA
    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.2f} MB"
    if value >= 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value} B"


def _retention_lines(snapshot: RetentionSnapshot | None) -> list[str]:
    """H-6.7 retention diagnostics block."""
    lines = [
        "RETENTION",
        "----------------------------------------",
    ]
    if snapshot is None:
        lines.extend(
            [
                f"Current Journal Entries {_NA}",
                f"Journal Limit           {_NA}",
                f"Checkpoint Versions     {_NA}",
                f"Version Limit           {_NA}",
                f"Snapshot Log Size       {_NA}",
                f"Snapshot Limit          {_NA}",
                f"Tick File Size          {_NA}",
                f"Tick Limit              {_NA}",
                f"DOM File Size           {_NA}",
                f"DOM Limit               {_NA}",
                f"Retention Events        {_NA}",
            ]
        )
        return lines
    lines.extend(
        [
            f"Current Journal Entries {snapshot.journal_entries}",
            f"Journal Limit           {snapshot.journal_limit}",
            f"Checkpoint Versions     {snapshot.checkpoint_versions}",
            f"Version Limit           {snapshot.version_limit}",
            f"Snapshot Log Size       {_fmt_bytes_size(snapshot.snapshot_log_size_bytes)}",
            f"Snapshot Limit          {_fmt_bytes_size(snapshot.snapshot_log_limit_bytes)}",
            f"Tick File Size          {_fmt_bytes_size(snapshot.tick_file_size_bytes)}",
            f"Tick Limit              {_fmt_bytes_size(snapshot.tick_file_limit_bytes)}",
            f"DOM File Size           {_fmt_bytes_size(snapshot.dom_file_size_bytes)}",
            f"DOM Limit               {_fmt_bytes_size(snapshot.dom_file_limit_bytes)}",
            f"Retention Events        {snapshot.retention_events}",
            "Note: hierarchy journal limits are advisory (never prune live AI state)",
        ]
    )
    return lines


def render_performance_page(
    timing: LoopTimingSnapshot | None,
    *,
    feed_status: str | None = None,
    ingress_poll: IngressPollSnapshot | None = None,
    retention: RetentionSnapshot | None = None,
) -> str:
    """Render the IDC Performance diagnostics page from existing timing only."""
    lines = [
        "==============================",
        "PERFORMANCE",
        "----------------------------------------",
        *_ingress_poll_lines(ingress_poll),
        "----------------------------------------",
        *_retention_lines(retention),
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
                f"Combined Checkpoint   {_NA}",
                f"Status            {_NA}",
                "----------------------------------------",
                *_checkpoint_exclusive_lines(0.0, None, sample_available=False),
                "----------------------------------------",
                *_breakdown_lines(
                    "Hierarchy Checkpoint",
                    0.0,
                    None,
                    sample_available=False,
                ),
                "----------------------------------------",
                *_logging_exclusive_lines(0.0, None, sample_available=False),
                "----------------------------------------",
                *_tick_retention_lines(None, sample_available=False),
                "----------------------------------------",
                *_hierarchy_footprint_lines(None, sample_available=False),
                "----------------------------------------",
                *_logging_footprint_lines(None, sample_available=False),
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
            f"Combined Checkpoint   {_fmt_ms(timing.checkpoint_ms)}",
            f"Status            {timing.checkpoint_severity.value}",
            "----------------------------------------",
            *_checkpoint_exclusive_lines(
                timing.checkpoint_ms,
                timing.checkpoint_exclusive,
                sample_available=True,
            ),
            "----------------------------------------",
            *_breakdown_lines(
                "Hierarchy Checkpoint",
                timing.hierarchy_checkpoint_ms,
                timing.hierarchy_breakdown,
                sample_available=True,
            ),
            "----------------------------------------",
            *_logging_exclusive_lines(
                timing.logging_ms,
                timing.logging_exclusive,
                sample_available=True,
            ),
            f"Status            {timing.logging_severity.value}",
            "----------------------------------------",
            *_tick_retention_lines(
                timing.tick_retention,
                sample_available=True,
            ),
            "----------------------------------------",
            *_hierarchy_footprint_lines(
                timing.hierarchy_footprint, sample_available=True
            ),
            "----------------------------------------",
            *_logging_footprint_lines(
                timing.logging_footprint, sample_available=True
            ),
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
