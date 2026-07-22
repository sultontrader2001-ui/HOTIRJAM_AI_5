"""Engineering session report — evidence summary only (not certification)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from hotirjam_ai5.objective_engineering.models import (
    ObjectiveAnomaly,
    ObjectiveChangeEvent,
    ObjectiveEngineeringSample,
)


@dataclass(frozen=True, slots=True)
class EngineeringSessionReport:
    """Phase A session summary. Never claims VALIDATED or CERTIFIED."""

    sample_count: int
    change_count: int
    anomaly_count: int
    duration_seconds: float
    anomaly_counts: tuple[tuple[str, int], ...]
    change_reason_counts: tuple[tuple[str, int], ...]
    out_dir: str
    workflow_verdict: str

    def as_text(self) -> str:
        lines = [
            "HOTIRJAM AI 5 — Objective Engine V2",
            "Engineering Validation Phase A — Session Report",
            "NOT Formal Validation. NOT Certification.",
            "",
            f"workflow_verdict: {self.workflow_verdict}",
            f"out_dir: {self.out_dir}",
            f"duration_seconds: {self.duration_seconds:.3f}",
            f"samples: {self.sample_count}",
            f"changes: {self.change_count}",
            f"anomalies: {self.anomaly_count}",
            "",
            "anomaly_counts:",
        ]
        if not self.anomaly_counts:
            lines.append("  (none)")
        else:
            for code, count in self.anomaly_counts:
                lines.append(f"  {code}: {count}")
        lines.append("")
        lines.append("change_reason_counts:")
        if not self.change_reason_counts:
            lines.append("  (none)")
        else:
            for reason, count in self.change_reason_counts:
                lines.append(f"  {reason}: {count}")
        lines.extend(
            [
                "",
                "Files: samples.ndjson, changes.ndjson, anomalies.ndjson",
                "Next: triage anomalies; then Formal Live Validation if clean.",
            ]
        )
        return "\n".join(lines)


def build_session_report(
    *,
    samples: tuple[ObjectiveEngineeringSample, ...],
    changes: tuple[ObjectiveChangeEvent, ...],
    anomalies: tuple[ObjectiveAnomaly, ...],
    duration_seconds: float,
    out_dir: Path,
) -> EngineeringSessionReport:
    anomaly_counter = Counter(a.code for a in anomalies)
    reason_counter = Counter(c.reason for c in changes)
    # Workflow PASS means evidence was collected (session ran). Anomalies are findings.
    workflow = "PASS" if len(samples) >= 1 else "FAIL_NO_SAMPLES"
    return EngineeringSessionReport(
        sample_count=len(samples),
        change_count=len(changes),
        anomaly_count=len(anomalies),
        duration_seconds=duration_seconds,
        anomaly_counts=tuple(sorted(anomaly_counter.items())),
        change_reason_counts=tuple(sorted(reason_counter.items())),
        out_dir=str(out_dir),
        workflow_verdict=workflow,
    )
