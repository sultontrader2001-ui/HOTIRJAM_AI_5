"""Format replay reports (H-8.1)."""

from __future__ import annotations

from hotirjam_ai5.replay.models import ObservationReplayResult, ReplayReport


def format_replay_report(report: ReplayReport) -> str:
    lines = [
        "HOTIRJAM AI 5 — H-8.1 Replay Validation Report",
        "=" * 60,
        f"Session Verdict: {report.verdict}",
        f"Fingerprint: {report.deterministic_fingerprint}",
        "",
        "Session Summary:",
    ]
    for row in report.summary_lines:
        lines.append(f"  {row}")
    lines.append("")
    lines.append("Replay Summary / Per Observation:")
    for result in report.results:
        lines.extend(_format_one(result))
        lines.append("")
    lines.append("Mode: REPLAY only · observations immutable · no orders")
    lines.append("=" * 60)
    return "\n".join(lines)


def _format_one(result: ObservationReplayResult) -> list[str]:
    return [
        f"  Cycle {result.cycle_id} @ t={result.observation_time:.3f} "
        f"(path={result.subsequent_points})",
        f"    Objective ........ {result.objective.value}",
        f"    Initiative ....... {result.initiative.value}",
        f"    Response ......... {result.response.value}",
        f"    Continuation ..... {result.continuation.value}",
        f"    Break Capability . {result.break_capability.value}",
        f"    Confidence ....... {result.confidence.value}",
        *[f"    · {n}" for n in result.notes],
    ]
