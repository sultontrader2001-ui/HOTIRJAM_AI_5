"""Passive Live Validator loop timing (H-6.6.4 / H-6.6.6).

Diagnostics only. Never changes execution order, polling, rendering,
checkpoints, or keyboard behavior. Instrumentation failures are ignored.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

SLOW_MS = 100.0
CRITICAL_MS = 1000.0


class TimingSeverity(StrEnum):
    OK = "OK"
    SLOW = "SLOW"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class StageBreakdown:
    """Internal stage timings for one write path.

    ``None`` means the stage does not exist in that path (NOT APPLICABLE).
    Values are milliseconds accumulated within the latest loop sample.
    """

    collect_ms: float | None
    build_ms: float | None
    serialize_ms: float | None
    write_ms: float | None
    flush_ms: float | None


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
    """Accumulate hierarchy checkpoint internal stage timings."""
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
    """Accumulate snapshot-logger internal stage timings."""
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
