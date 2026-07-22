"""H-6.9 — Snapshot Logger evidence probe (instrumentation only).

Records per-record exclusive phase timings and optional loop correlations.
Never changes SnapshotLogger outputs, persistence, or APIs.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass(frozen=True, slots=True)
class SnapshotLoggerPhaseSample:
    """One SnapshotLogger.log() observation."""

    frame_prep_ms: float
    diagnostics_attachment_ms: float
    serialize_ms: float
    write_ms: float
    flush_ms: float
    rotation_check_ms: float
    reopen_ms: float
    total_ms: float
    # Correlation fields (filled by harness / loop seal when available).
    loop_ms: float | None = None
    poll_ms: float | None = None
    checkpoint_ms: float | None = None


@dataclass(frozen=True, slots=True)
class PhaseStats:
    name: str
    count: int
    minimum: float
    maximum: float
    average: float
    median: float
    p95: float
    p99: float
    stddev: float
    total: float


@dataclass(frozen=True, slots=True)
class SnapshotLoggerEvidenceReport:
    samples: tuple[SnapshotLoggerPhaseSample, ...]
    phase_stats: tuple[PhaseStats, ...]
    phase_rank_by_total: tuple[tuple[str, float, float], ...]  # name, total, pct_of_logger
    mean_logger_ms: float
    mean_loop_ms: float | None
    mean_poll_ms: float | None
    mean_checkpoint_ms: float | None
    mean_logger_share_of_loop: float | None  # 0..1
    contribution_class: str
    correlation_logger_vs_loop: float | None
    correlation_logger_vs_poll: float | None
    correlation_logger_vs_checkpoint: float | None
    hottest_phase: str | None
    verdict: str
    notes: tuple[str, ...] = ()


_enabled = True
_samples: list[SnapshotLoggerPhaseSample] = []


def reset_snapshot_logger_probe_for_tests() -> None:
    global _samples, _enabled
    _samples = []
    _enabled = True


def set_snapshot_logger_probe_enabled(enabled: bool) -> None:
    global _enabled
    _enabled = bool(enabled)


def snapshot_logger_samples() -> tuple[SnapshotLoggerPhaseSample, ...]:
    return tuple(_samples)


def record_snapshot_logger_phases(
    *,
    frame_prep_ms: float,
    diagnostics_attachment_ms: float,
    serialize_ms: float,
    write_ms: float,
    flush_ms: float,
    rotation_check_ms: float,
    reopen_ms: float,
    total_ms: float,
) -> None:
    """Append one exclusive-phase sample. Failures are ignored."""
    try:
        if not _enabled:
            return
        _samples.append(
            SnapshotLoggerPhaseSample(
                frame_prep_ms=max(0.0, float(frame_prep_ms)),
                diagnostics_attachment_ms=max(0.0, float(diagnostics_attachment_ms)),
                serialize_ms=max(0.0, float(serialize_ms)),
                write_ms=max(0.0, float(write_ms)),
                flush_ms=max(0.0, float(flush_ms)),
                rotation_check_ms=max(0.0, float(rotation_check_ms)),
                reopen_ms=max(0.0, float(reopen_ms)),
                total_ms=max(0.0, float(total_ms)),
            )
        )
    except Exception:
        return


def attach_correlation_to_last_sample(
    *,
    loop_ms: float | None,
    poll_ms: float | None,
    checkpoint_ms: float | None,
) -> None:
    """Attach loop/poll/checkpoint correlation to the latest logger sample."""
    try:
        if not _samples:
            return
        last = _samples[-1]
        _samples[-1] = SnapshotLoggerPhaseSample(
            frame_prep_ms=last.frame_prep_ms,
            diagnostics_attachment_ms=last.diagnostics_attachment_ms,
            serialize_ms=last.serialize_ms,
            write_ms=last.write_ms,
            flush_ms=last.flush_ms,
            rotation_check_ms=last.rotation_check_ms,
            reopen_ms=last.reopen_ms,
            total_ms=last.total_ms,
            loop_ms=None if loop_ms is None else float(loop_ms),
            poll_ms=None if poll_ms is None else float(poll_ms),
            checkpoint_ms=None if checkpoint_ms is None else float(checkpoint_ms),
        )
    except Exception:
        return


def _percentile(sorted_vals: Sequence[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    rank = (p / 100.0) * (len(sorted_vals) - 1)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return float(sorted_vals[lo])
    weight = rank - lo
    return float(sorted_vals[lo] * (1.0 - weight) + sorted_vals[hi] * weight)


def _stats_for(name: str, values: Sequence[float]) -> PhaseStats:
    if not values:
        return PhaseStats(
            name=name,
            count=0,
            minimum=0.0,
            maximum=0.0,
            average=0.0,
            median=0.0,
            p95=0.0,
            p99=0.0,
            stddev=0.0,
            total=0.0,
        )
    ordered = sorted(float(v) for v in values)
    avg = statistics.fmean(ordered)
    stdev = statistics.pstdev(ordered) if len(ordered) > 1 else 0.0
    return PhaseStats(
        name=name,
        count=len(ordered),
        minimum=ordered[0],
        maximum=ordered[-1],
        average=avg,
        median=statistics.median(ordered),
        p95=_percentile(ordered, 95.0),
        p99=_percentile(ordered, 99.0),
        stddev=stdev,
        total=sum(ordered),
    )


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if den_x == 0.0 or den_y == 0.0:
        return None
    return num / (den_x * den_y)


def _contribution_class(share: float | None) -> str:
    if share is None:
        return "UNKNOWN"
    pct = share * 100.0
    if pct < 10.0:
        return "<10%"
    if pct < 25.0:
        return "10–25%"
    if pct < 50.0:
        return "25–50%"
    return ">50%"


def _verdict(share: float | None, hottest: str | None) -> str:
    """Primary-bottleneck verdict for Snapshot Logger after H-6.8.2."""
    if share is None:
        return "REJECTED"
    if share > 0.50:
        return "CONFIRMED"
    if share >= 0.25:
        return "PARTIALLY CONFIRMED"
    # Logger is largest internal phase but still small vs loop → not primary.
    if hottest is not None and share >= 0.10:
        return "PARTIALLY CONFIRMED"
    return "REJECTED"


def build_snapshot_logger_evidence_report() -> SnapshotLoggerEvidenceReport:
    samples = tuple(_samples)
    phase_names = (
        ("frame_prep_ms", "Frame preparation"),
        ("diagnostics_attachment_ms", "Objective diagnostics attachment"),
        ("serialize_ms", "Serialization"),
        ("write_ms", "NDJSON write"),
        ("flush_ms", "Flush"),
        ("rotation_check_ms", "Rotation check"),
        ("reopen_ms", "Reopen"),
        ("total_ms", "Total Snapshot Logger"),
    )
    phase_stats_list: list[PhaseStats] = []
    for attr, label in phase_names:
        values = [getattr(s, attr) for s in samples]
        phase_stats_list.append(_stats_for(label, values))

    logger_total = next(p for p in phase_stats_list if p.name == "Total Snapshot Logger")
    # Rank exclusive phases only (exclude Total).
    exclusive = [p for p in phase_stats_list if p.name != "Total Snapshot Logger"]
    denom = logger_total.total if logger_total.total > 0 else 1.0
    ranked = sorted(exclusive, key=lambda p: p.total, reverse=True)
    phase_rank = tuple(
        (p.name, p.total, (p.total / denom) * 100.0) for p in ranked
    )
    hottest = ranked[0].name if ranked else None

    correlated = [s for s in samples if s.loop_ms is not None and s.loop_ms > 0]
    mean_logger = logger_total.average
    mean_loop = (
        statistics.fmean([s.loop_ms for s in correlated if s.loop_ms is not None])
        if correlated
        else None
    )
    mean_poll = (
        statistics.fmean([s.poll_ms for s in correlated if s.poll_ms is not None])
        if correlated and any(s.poll_ms is not None for s in correlated)
        else None
    )
    mean_checkpoint = (
        statistics.fmean(
            [s.checkpoint_ms for s in correlated if s.checkpoint_ms is not None]
        )
        if correlated and any(s.checkpoint_ms is not None for s in correlated)
        else None
    )
    share = None
    if mean_loop is not None and mean_loop > 0:
        share = mean_logger / mean_loop

    logger_vals = [s.total_ms for s in correlated]
    loop_vals = [float(s.loop_ms) for s in correlated if s.loop_ms is not None]
    poll_vals = [
        float(s.poll_ms) for s in correlated if s.poll_ms is not None
    ]
    ck_vals = [
        float(s.checkpoint_ms) for s in correlated if s.checkpoint_ms is not None
    ]

    notes = (
        "Frame preparation = _jsonable of all ValidatorFrame fields except objective_diagnostics.",
        "Objective diagnostics attachment = _jsonable of objective_diagnostics only "
        "(document inclusion cost inside log; H-6.8.2 reference attach is outside logger).",
        "Phases are exclusive; footprint diagnostics are outside sealed logger total.",
    )

    return SnapshotLoggerEvidenceReport(
        samples=samples,
        phase_stats=tuple(phase_stats_list),
        phase_rank_by_total=phase_rank,
        mean_logger_ms=mean_logger,
        mean_loop_ms=mean_loop,
        mean_poll_ms=mean_poll,
        mean_checkpoint_ms=mean_checkpoint,
        mean_logger_share_of_loop=share,
        contribution_class=_contribution_class(share),
        correlation_logger_vs_loop=_pearson(logger_vals, loop_vals),
        correlation_logger_vs_poll=_pearson(logger_vals, poll_vals)
        if len(poll_vals) == len(logger_vals)
        else None,
        correlation_logger_vs_checkpoint=_pearson(logger_vals, ck_vals)
        if len(ck_vals) == len(logger_vals)
        else None,
        hottest_phase=hottest,
        verdict=_verdict(share, hottest),
        notes=notes,
    )


def render_snapshot_logger_evidence_report(
    report: SnapshotLoggerEvidenceReport | None = None,
) -> str:
    report = report or build_snapshot_logger_evidence_report()
    lines = [
        "HOTIRJAM AI 5",
        "Sprint H-6.9 — Snapshot Logger Certification",
        "====================================================",
        "EVIDENCE REPORT",
        "====================================================",
        "",
        f"VERDICT: {report.verdict}",
        f"Contribution class (logger / loop): {report.contribution_class}",
        f"Samples: {len(report.samples)}",
        "",
        "ARCHITECTURE (post H-6.8.2)",
        "  Tick → pipeline.evaluate (diagnostics reference attach)",
        "       → SnapshotLogger.log",
        "            → Frame prep (_jsonable non-diag fields)",
        "            → Diagnostics attachment (_jsonable diagnostics)",
        "            → Serialization (json.dumps)",
        "            → NDJSON write",
        "            → Flush",
        "            → Rotation check",
        "            → Reopen (if rotated)",
        "",
        "TIMING TABLE (ms)",
        f"{'Phase':<36} {'N':>5} {'Min':>10} {'Max':>10} {'Avg':>10} "
        f"{'Med':>10} {'P95':>10} {'P99':>10} {'Std':>10} {'Total':>12}",
    ]
    for p in report.phase_stats:
        lines.append(
            f"{p.name:<36} {p.count:>5} {p.minimum:>10.4f} {p.maximum:>10.4f} "
            f"{p.average:>10.4f} {p.median:>10.4f} {p.p95:>10.4f} {p.p99:>10.4f} "
            f"{p.stddev:>10.4f} {p.total:>12.4f}"
        )

    lines.extend(["", "PHASE RANKING (by total contribution to logger)"])
    for i, (name, total, pct) in enumerate(report.phase_rank_by_total, start=1):
        lines.append(f"  {i}. {name:<36} total={total:.4f} ms  ({pct:.2f}% of logger)")

    lines.extend(
        [
            "",
            "CORRELATION / MEANS",
            f"  Mean logger ms.............. {report.mean_logger_ms:.4f}",
            f"  Mean loop ms................ {_fmt(report.mean_loop_ms)}",
            f"  Mean poll_once ms........... {_fmt(report.mean_poll_ms)}",
            f"  Mean checkpoint ms.......... {_fmt(report.mean_checkpoint_ms)}",
            f"  Logger share of loop........ {_fmt_pct(report.mean_logger_share_of_loop)}",
            f"  Corr(logger, loop).......... {_fmt(report.correlation_logger_vs_loop)}",
            f"  Corr(logger, poll).......... {_fmt(report.correlation_logger_vs_poll)}",
            f"  Corr(logger, checkpoint).... {_fmt(report.correlation_logger_vs_checkpoint)}",
            f"  Hottest phase............... {report.hottest_phase or 'N/A'}",
            "",
            "NOTES",
        ]
    )
    for note in report.notes:
        lines.append(f"  - {note}")
    lines.append("")
    return "\n".join(lines)


def _fmt(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.4f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100.0:.2f}%"
