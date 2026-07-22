"""Passive Live Validator loop timing (H-6.6.4 / H-6.6.6 / H-6.7.1).

Diagnostics only. Never changes execution order, polling, rendering,
checkpoints, or keyboard behavior. Instrumentation failures are ignored.

H-6.7.1: exclusive stage timings (no overlapping timers).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

SLOW_MS = 100.0
CRITICAL_MS = 1000.0


class TimingSeverity(StrEnum):
    OK = "OK"
    SLOW = "SLOW"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class LoggingExclusiveBreakdown:
    """Exclusive Snapshot Logger stages (H-6.7.1). Milliseconds; non-overlapping."""

    build_ms: float
    serialize_ms: float
    write_ms: float
    flush_ms: float
    rotate_ms: float
    reopen_ms: float


@dataclass(frozen=True, slots=True)
class CheckpointExclusiveBreakdown:
    """Exclusive Combined Checkpoint stages (H-6.7.1).

    ``serialize_ms`` is ``None`` when the path has no distinct serialize step
    (hierarchy assembles a pre-built JSON document string).
    """

    assemble_ms: float
    serialize_ms: float | None
    write_ms: float
    flush_ms: float
    fsync_ms: float
    os_replace_ms: float


@dataclass(frozen=True, slots=True)
class TickRetentionBreakdown:
    """Exclusive tick NDJSON retention stages (H-6.7.1). Non-overlapping."""

    total_ms: float
    stat_ms: float
    read_ms: float
    write_ms: float
    fsync_ms: float
    replace_ms: float


# Backward-compatible alias used by older tests/imports.
@dataclass(frozen=True, slots=True)
class StageBreakdown:
    """Legacy stage timings. Prefer exclusive breakdown types (H-6.7.1)."""

    collect_ms: float | None
    build_ms: float | None
    serialize_ms: float | None
    write_ms: float | None
    flush_ms: float | None


@dataclass(frozen=True, slots=True)
class SectionSize:
    """One top-level JSON section and its encoded size in bytes."""

    name: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class HierarchyFootprint:
    """What the hierarchy checkpoint serialized (latest write in the sample)."""

    registry_entries: int
    hierarchy_nodes: int
    journal_entries: int
    snapshot_object_count: int
    json_size_bytes: int
    section_sizes: tuple[SectionSize, ...]
    largest_section: str | None
    largest_section_bytes: int | None

    @property
    def json_size_mb(self) -> float:
        return self.json_size_bytes / (1024.0 * 1024.0)


@dataclass(frozen=True, slots=True)
class LoggingFootprint:
    """What the snapshot logger serialized (latest write in the sample)."""

    frame_object_count: int
    top_level_sections: tuple[str, ...]
    json_size_bytes: int
    section_sizes: tuple[SectionSize, ...]
    largest_section: str | None
    largest_section_bytes: int | None

    @property
    def json_size_mb(self) -> float:
        return self.json_size_bytes / (1024.0 * 1024.0)


@dataclass(frozen=True, slots=True)
class LoopTimingSnapshot:
    """Latest main-loop timing sample. Read-only observation artifact."""

    loop_ms: float
    poll_ms: float
    keyboard_ms: float
    render_ms: float
    sleep_ms: float
    checkpoint_ms: float
    initiative_checkpoint_ms: float
    hierarchy_checkpoint_ms: float
    logging_ms: float
    start_time: float
    end_time: float
    poll_severity: TimingSeverity
    keyboard_severity: TimingSeverity
    render_severity: TimingSeverity
    sleep_severity: TimingSeverity
    checkpoint_severity: TimingSeverity
    initiative_checkpoint_severity: TimingSeverity
    hierarchy_checkpoint_severity: TimingSeverity
    logging_severity: TimingSeverity
    loop_severity: TimingSeverity
    hierarchy_breakdown: StageBreakdown | None = None
    logging_breakdown: StageBreakdown | None = None
    hierarchy_footprint: HierarchyFootprint | None = None
    logging_footprint: LoggingFootprint | None = None
    # H-6.7.1 exclusive stage breakdowns
    logging_exclusive: LoggingExclusiveBreakdown | None = None
    checkpoint_exclusive: CheckpointExclusiveBreakdown | None = None
    tick_retention: TickRetentionBreakdown | None = None

    def stage_severity(self, stage: str) -> TimingSeverity:
        """Return severity for a named stage, or OK if unknown."""
        mapping = {
            "loop": self.loop_severity,
            "poll": self.poll_severity,
            "keyboard": self.keyboard_severity,
            "render": self.render_severity,
            "sleep": self.sleep_severity,
            "checkpoint": self.checkpoint_severity,
            "initiative_checkpoint": self.initiative_checkpoint_severity,
            "hierarchy_checkpoint": self.hierarchy_checkpoint_severity,
            "logging": self.logging_severity,
        }
        return mapping.get(stage, TimingSeverity.OK)


def severity_for_ms(elapsed_ms: float) -> TimingSeverity:
    if elapsed_ms >= CRITICAL_MS:
        return TimingSeverity.CRITICAL
    if elapsed_ms >= SLOW_MS:
        return TimingSeverity.SLOW
    return TimingSeverity.OK


def _sum_optional(current: float | None, delta: float | None) -> float | None:
    if delta is None:
        return current
    if current is None:
        return max(0.0, float(delta))
    return float(current) + max(0.0, float(delta))


def _sum_float(current: float, delta: float) -> float:
    return float(current) + max(0.0, float(delta))


class _LoopTimingAccumulator:
    """Mutable per-iteration counters. Not part of the public API."""

    __slots__ = (
        "start_time",
        "poll_ms",
        "keyboard_ms",
        "render_ms",
        "sleep_ms",
        "initiative_checkpoint_ms",
        "hierarchy_checkpoint_ms",
        "logging_ms",
        "hierarchy_collect_ms",
        "hierarchy_build_ms",
        "hierarchy_serialize_ms",
        "hierarchy_write_ms",
        "hierarchy_flush_ms",
        "logging_collect_ms",
        "logging_build_ms",
        "logging_serialize_ms",
        "logging_write_ms",
        "logging_flush_ms",
        "hierarchy_breakdown_seen",
        "logging_breakdown_seen",
        "hierarchy_footprint",
        "logging_footprint",
        # H-6.7.1 exclusive
        "logging_build_ex_ms",
        "logging_serialize_ex_ms",
        "logging_write_ex_ms",
        "logging_flush_ex_ms",
        "logging_rotate_ex_ms",
        "logging_reopen_ex_ms",
        "logging_exclusive_seen",
        "checkpoint_assemble_ms",
        "checkpoint_serialize_ms",
        "checkpoint_write_ms",
        "checkpoint_flush_ms",
        "checkpoint_fsync_ms",
        "checkpoint_os_replace_ms",
        "checkpoint_exclusive_seen",
        "checkpoint_serialize_applicable",
        "tick_retention_total_ms",
        "tick_retention_stat_ms",
        "tick_retention_read_ms",
        "tick_retention_write_ms",
        "tick_retention_fsync_ms",
        "tick_retention_replace_ms",
        "tick_retention_seen",
    )

    def __init__(self, *, start_time: float) -> None:
        self.start_time = start_time
        self.poll_ms = 0.0
        self.keyboard_ms = 0.0
        self.render_ms = 0.0
        self.sleep_ms = 0.0
        self.initiative_checkpoint_ms = 0.0
        self.hierarchy_checkpoint_ms = 0.0
        self.logging_ms = 0.0
        self.hierarchy_collect_ms: float | None = None
        self.hierarchy_build_ms: float | None = None
        self.hierarchy_serialize_ms: float | None = None
        self.hierarchy_write_ms: float | None = None
        self.hierarchy_flush_ms: float | None = None
        self.logging_collect_ms: float | None = None
        self.logging_build_ms: float | None = None
        self.logging_serialize_ms: float | None = None
        self.logging_write_ms: float | None = None
        self.logging_flush_ms: float | None = None
        self.hierarchy_breakdown_seen = False
        self.logging_breakdown_seen = False
        self.hierarchy_footprint: HierarchyFootprint | None = None
        self.logging_footprint: LoggingFootprint | None = None
        self.logging_build_ex_ms = 0.0
        self.logging_serialize_ex_ms = 0.0
        self.logging_write_ex_ms = 0.0
        self.logging_flush_ex_ms = 0.0
        self.logging_rotate_ex_ms = 0.0
        self.logging_reopen_ex_ms = 0.0
        self.logging_exclusive_seen = False
        self.checkpoint_assemble_ms = 0.0
        self.checkpoint_serialize_ms: float | None = None
        self.checkpoint_write_ms = 0.0
        self.checkpoint_flush_ms = 0.0
        self.checkpoint_fsync_ms = 0.0
        self.checkpoint_os_replace_ms = 0.0
        self.checkpoint_exclusive_seen = False
        self.checkpoint_serialize_applicable = False
        self.tick_retention_total_ms = 0.0
        self.tick_retention_stat_ms = 0.0
        self.tick_retention_read_ms = 0.0
        self.tick_retention_write_ms = 0.0
        self.tick_retention_fsync_ms = 0.0
        self.tick_retention_replace_ms = 0.0
        self.tick_retention_seen = False

    def build(self, *, end_time: float) -> LoopTimingSnapshot:
        checkpoint_ms = self.initiative_checkpoint_ms + self.hierarchy_checkpoint_ms
        loop_ms = max(0.0, (end_time - self.start_time) * 1000.0)
        hierarchy_breakdown = None
        if self.hierarchy_breakdown_seen:
            hierarchy_breakdown = StageBreakdown(
                collect_ms=self.hierarchy_collect_ms,
                build_ms=self.hierarchy_build_ms,
                serialize_ms=self.hierarchy_serialize_ms,
                write_ms=self.hierarchy_write_ms,
                flush_ms=self.hierarchy_flush_ms,
            )
        logging_breakdown = None
        if self.logging_breakdown_seen:
            logging_breakdown = StageBreakdown(
                collect_ms=self.logging_collect_ms,
                build_ms=self.logging_build_ms,
                serialize_ms=self.logging_serialize_ms,
                write_ms=self.logging_write_ms,
                flush_ms=self.logging_flush_ms,
            )
        logging_exclusive = None
        if self.logging_exclusive_seen:
            logging_exclusive = LoggingExclusiveBreakdown(
                build_ms=self.logging_build_ex_ms,
                serialize_ms=self.logging_serialize_ex_ms,
                write_ms=self.logging_write_ex_ms,
                flush_ms=self.logging_flush_ex_ms,
                rotate_ms=self.logging_rotate_ex_ms,
                reopen_ms=self.logging_reopen_ex_ms,
            )
        checkpoint_exclusive = None
        if self.checkpoint_exclusive_seen:
            serialize: float | None
            if self.checkpoint_serialize_applicable:
                serialize = (
                    0.0
                    if self.checkpoint_serialize_ms is None
                    else self.checkpoint_serialize_ms
                )
            else:
                serialize = None
            checkpoint_exclusive = CheckpointExclusiveBreakdown(
                assemble_ms=self.checkpoint_assemble_ms,
                serialize_ms=serialize,
                write_ms=self.checkpoint_write_ms,
                flush_ms=self.checkpoint_flush_ms,
                fsync_ms=self.checkpoint_fsync_ms,
                os_replace_ms=self.checkpoint_os_replace_ms,
            )
        tick_retention = None
        if self.tick_retention_seen:
            tick_retention = TickRetentionBreakdown(
                total_ms=self.tick_retention_total_ms,
                stat_ms=self.tick_retention_stat_ms,
                read_ms=self.tick_retention_read_ms,
                write_ms=self.tick_retention_write_ms,
                fsync_ms=self.tick_retention_fsync_ms,
                replace_ms=self.tick_retention_replace_ms,
            )
        return LoopTimingSnapshot(
            loop_ms=loop_ms,
            poll_ms=self.poll_ms,
            keyboard_ms=self.keyboard_ms,
            render_ms=self.render_ms,
            sleep_ms=self.sleep_ms,
            checkpoint_ms=checkpoint_ms,
            initiative_checkpoint_ms=self.initiative_checkpoint_ms,
            hierarchy_checkpoint_ms=self.hierarchy_checkpoint_ms,
            logging_ms=self.logging_ms,
            start_time=self.start_time,
            end_time=end_time,
            poll_severity=severity_for_ms(self.poll_ms),
            keyboard_severity=severity_for_ms(self.keyboard_ms),
            render_severity=severity_for_ms(self.render_ms),
            sleep_severity=severity_for_ms(self.sleep_ms),
            checkpoint_severity=severity_for_ms(checkpoint_ms),
            initiative_checkpoint_severity=severity_for_ms(
                self.initiative_checkpoint_ms
            ),
            hierarchy_checkpoint_severity=severity_for_ms(
                self.hierarchy_checkpoint_ms
            ),
            logging_severity=severity_for_ms(self.logging_ms),
            loop_severity=severity_for_ms(loop_ms),
            hierarchy_breakdown=hierarchy_breakdown,
            logging_breakdown=logging_breakdown,
            hierarchy_footprint=self.hierarchy_footprint,
            logging_footprint=self.logging_footprint,
            logging_exclusive=logging_exclusive,
            checkpoint_exclusive=checkpoint_exclusive,
            tick_retention=tick_retention,
        )


# Only the active iteration accumulator (no history / growing buffers).
_active: _LoopTimingAccumulator | None = None
_latest: LoopTimingSnapshot | None = None


def latest_loop_timing() -> LoopTimingSnapshot | None:
    """Read-only view of the most recent completed loop sample."""
    return _latest


def begin_loop_sample() -> None:
    """Start a new iteration sample. Replaces any incomplete sample."""
    global _active
    try:
        _active = _LoopTimingAccumulator(start_time=time.perf_counter())
    except Exception:
        _active = None


def finish_loop_sample() -> LoopTimingSnapshot | None:
    """Seal the active sample as the sole stored snapshot."""
    global _active, _latest
    try:
        acc = _active
        _active = None
        if acc is None:
            return _latest
        _latest = acc.build(end_time=time.perf_counter())
        return _latest
    except Exception:
        _active = None
        return _latest


def _add_ms(attr: str, elapsed_ms: float) -> None:
    try:
        acc = _active
        if acc is None:
            return
        current = getattr(acc, attr, 0.0)
        setattr(acc, attr, float(current) + max(0.0, float(elapsed_ms)))
    except Exception:
        return


def add_poll_ms(elapsed_ms: float) -> None:
    _add_ms("poll_ms", elapsed_ms)


def add_keyboard_ms(elapsed_ms: float) -> None:
    _add_ms("keyboard_ms", elapsed_ms)


def add_render_ms(elapsed_ms: float) -> None:
    _add_ms("render_ms", elapsed_ms)


def add_sleep_ms(elapsed_ms: float) -> None:
    _add_ms("sleep_ms", elapsed_ms)


def add_initiative_checkpoint_ms(elapsed_ms: float) -> None:
    _add_ms("initiative_checkpoint_ms", elapsed_ms)


def add_hierarchy_checkpoint_ms(elapsed_ms: float) -> None:
    _add_ms("hierarchy_checkpoint_ms", elapsed_ms)


def add_logging_ms(elapsed_ms: float) -> None:
    _add_ms("logging_ms", elapsed_ms)


def add_hierarchy_breakdown(
    *,
    collect_ms: float | None = None,
    build_ms: float | None = None,
    serialize_ms: float | None = None,
    write_ms: float | None = None,
    flush_ms: float | None = None,
) -> None:
    """Accumulate hierarchy checkpoint internal stage timings (legacy)."""
    try:
        acc = _active
        if acc is None:
            return
        acc.hierarchy_breakdown_seen = True
        acc.hierarchy_collect_ms = _sum_optional(acc.hierarchy_collect_ms, collect_ms)
        acc.hierarchy_build_ms = _sum_optional(acc.hierarchy_build_ms, build_ms)
        acc.hierarchy_serialize_ms = _sum_optional(
            acc.hierarchy_serialize_ms, serialize_ms
        )
        acc.hierarchy_write_ms = _sum_optional(acc.hierarchy_write_ms, write_ms)
        acc.hierarchy_flush_ms = _sum_optional(acc.hierarchy_flush_ms, flush_ms)
    except Exception:
        return


def add_logging_breakdown(
    *,
    collect_ms: float | None = None,
    build_ms: float | None = None,
    serialize_ms: float | None = None,
    write_ms: float | None = None,
    flush_ms: float | None = None,
) -> None:
    """Accumulate snapshot-logger internal stage timings (legacy)."""
    try:
        acc = _active
        if acc is None:
            return
        acc.logging_breakdown_seen = True
        acc.logging_collect_ms = _sum_optional(acc.logging_collect_ms, collect_ms)
        acc.logging_build_ms = _sum_optional(acc.logging_build_ms, build_ms)
        acc.logging_serialize_ms = _sum_optional(acc.logging_serialize_ms, serialize_ms)
        acc.logging_write_ms = _sum_optional(acc.logging_write_ms, write_ms)
        acc.logging_flush_ms = _sum_optional(acc.logging_flush_ms, flush_ms)
    except Exception:
        return


def add_logging_exclusive(
    *,
    build_ms: float = 0.0,
    serialize_ms: float = 0.0,
    write_ms: float = 0.0,
    flush_ms: float = 0.0,
    rotate_ms: float = 0.0,
    reopen_ms: float = 0.0,
) -> None:
    """Accumulate exclusive Snapshot Logger stages (H-6.7.1)."""
    try:
        acc = _active
        if acc is None:
            return
        acc.logging_exclusive_seen = True
        acc.logging_build_ex_ms = _sum_float(acc.logging_build_ex_ms, build_ms)
        acc.logging_serialize_ex_ms = _sum_float(
            acc.logging_serialize_ex_ms, serialize_ms
        )
        acc.logging_write_ex_ms = _sum_float(acc.logging_write_ex_ms, write_ms)
        acc.logging_flush_ex_ms = _sum_float(acc.logging_flush_ex_ms, flush_ms)
        acc.logging_rotate_ex_ms = _sum_float(acc.logging_rotate_ex_ms, rotate_ms)
        acc.logging_reopen_ex_ms = _sum_float(acc.logging_reopen_ex_ms, reopen_ms)
    except Exception:
        return


def add_checkpoint_exclusive(
    *,
    assemble_ms: float = 0.0,
    serialize_ms: float | None = None,
    write_ms: float = 0.0,
    flush_ms: float = 0.0,
    fsync_ms: float = 0.0,
    os_replace_ms: float = 0.0,
) -> None:
    """Accumulate exclusive Combined Checkpoint stages (H-6.7.1).

    Pass ``serialize_ms=None`` when the path has no distinct serialize step.
    Pass a float (including 0.0) when serialize applies.
    """
    try:
        acc = _active
        if acc is None:
            return
        acc.checkpoint_exclusive_seen = True
        acc.checkpoint_assemble_ms = _sum_float(acc.checkpoint_assemble_ms, assemble_ms)
        if serialize_ms is not None:
            acc.checkpoint_serialize_applicable = True
            acc.checkpoint_serialize_ms = _sum_optional(
                acc.checkpoint_serialize_ms, serialize_ms
            )
        acc.checkpoint_write_ms = _sum_float(acc.checkpoint_write_ms, write_ms)
        acc.checkpoint_flush_ms = _sum_float(acc.checkpoint_flush_ms, flush_ms)
        acc.checkpoint_fsync_ms = _sum_float(acc.checkpoint_fsync_ms, fsync_ms)
        acc.checkpoint_os_replace_ms = _sum_float(
            acc.checkpoint_os_replace_ms, os_replace_ms
        )
    except Exception:
        return


def add_tick_retention_breakdown(
    *,
    total_ms: float = 0.0,
    stat_ms: float = 0.0,
    read_ms: float = 0.0,
    write_ms: float = 0.0,
    fsync_ms: float = 0.0,
    replace_ms: float = 0.0,
) -> None:
    """Accumulate exclusive tick retention stages (H-6.7.1)."""
    try:
        acc = _active
        if acc is None:
            return
        acc.tick_retention_seen = True
        acc.tick_retention_total_ms = _sum_float(
            acc.tick_retention_total_ms, total_ms
        )
        acc.tick_retention_stat_ms = _sum_float(acc.tick_retention_stat_ms, stat_ms)
        acc.tick_retention_read_ms = _sum_float(acc.tick_retention_read_ms, read_ms)
        acc.tick_retention_write_ms = _sum_float(acc.tick_retention_write_ms, write_ms)
        acc.tick_retention_fsync_ms = _sum_float(acc.tick_retention_fsync_ms, fsync_ms)
        acc.tick_retention_replace_ms = _sum_float(
            acc.tick_retention_replace_ms, replace_ms
        )
    except Exception:
        return


def _section_sizes(payload: Mapping[str, Any]) -> tuple[SectionSize, ...]:
    """Diagnostic sizes of top-level sections. Does not replace production serialize."""
    sizes: list[SectionSize] = []
    for name, value in payload.items():
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
        sizes.append(SectionSize(name=str(name), size_bytes=len(encoded.encode("utf-8"))))
    sizes.sort(key=lambda item: item.size_bytes, reverse=True)
    return tuple(sizes)


def _container_object_count(value: Any) -> int:
    """Count dict/list containers in a JSON-like structure."""
    if isinstance(value, dict):
        return 1 + sum(_container_object_count(item) for item in value.values())
    if isinstance(value, list):
        return 1 + sum(_container_object_count(item) for item in value)
    return 0


def set_hierarchy_footprint(
    *,
    payload: Mapping[str, Any],
    json_size_bytes: int | None = None,
    section_sizes: tuple[SectionSize, ...] | None = None,
) -> None:
    """Record hierarchy checkpoint footprint after timing has been sealed."""
    try:
        acc = _active
        if acc is None:
            return
        records = payload.get("records", ())
        journal = payload.get("journal", ())
        registry_entries = len(records) if hasattr(records, "__len__") else 0
        journal_entries = len(journal) if hasattr(journal, "__len__") else 0
        sections = section_sizes if section_sizes is not None else _section_sizes(payload)
        # Rank largest-first for display (cached section order may differ).
        sections = tuple(sorted(sections, key=lambda item: item.size_bytes, reverse=True))
        if json_size_bytes is None:
            json_size_bytes = sum(section.size_bytes for section in sections)
        largest = sections[0] if sections else None
        acc.hierarchy_footprint = HierarchyFootprint(
            registry_entries=registry_entries,
            hierarchy_nodes=registry_entries,
            journal_entries=journal_entries,
            snapshot_object_count=registry_entries,
            json_size_bytes=int(json_size_bytes),
            section_sizes=sections,
            largest_section=None if largest is None else largest.name,
            largest_section_bytes=None if largest is None else largest.size_bytes,
        )
    except Exception:
        return


def set_logging_footprint(
    *,
    payload: Mapping[str, Any],
    json_size_bytes: int,
) -> None:
    """Record snapshot-logger footprint after timing has been sealed."""
    try:
        acc = _active
        if acc is None:
            return
        sections = _section_sizes(payload)
        largest = sections[0] if sections else None
        acc.logging_footprint = LoggingFootprint(
            frame_object_count=_container_object_count(payload),
            top_level_sections=tuple(str(key) for key in payload.keys()),
            json_size_bytes=int(json_size_bytes),
            section_sizes=sections,
            largest_section=None if largest is None else largest.name,
            largest_section_bytes=None if largest is None else largest.size_bytes,
        )
    except Exception:
        return


def measure_ms(fn: Any) -> tuple[Any, float]:
    """Run ``fn`` and return ``(result, elapsed_ms)``. Never alters ``fn`` semantics."""
    started = time.perf_counter()
    result = fn()
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return result, elapsed_ms


def reset_loop_timing_for_tests() -> None:
    """Test helper: clear active + latest samples."""
    global _active, _latest
    _active = None
    _latest = None
