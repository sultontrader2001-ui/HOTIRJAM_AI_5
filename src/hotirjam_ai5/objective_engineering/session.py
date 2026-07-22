"""Engineering Validation session — live ticks via existing Live Validator controller."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from hotirjam_ai5.objective_engineering.recorder import ObjectiveEngineeringRecorder
from hotirjam_ai5.objective_engineering.report import (
    EngineeringSessionReport,
    build_session_report,
)


@dataclass
class EngineeringValidationSession:
    """Run one engineering live session. Never certifies. Never changes Objective."""

    out_dir: Path
    flicker_window: int = 3
    anomaly_stream: TextIO | None = None
    clock: Callable[[], float] | None = None

    def __post_init__(self) -> None:
        self.out_dir = Path(self.out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        stream = self.anomaly_stream
        if stream is None:
            import sys

            stream = sys.stderr
        self._recorder = ObjectiveEngineeringRecorder(
            samples_path=self.out_dir / "samples.ndjson",
            changes_path=self.out_dir / "changes.ndjson",
            anomalies_path=self.out_dir / "anomalies.ndjson",
            anomaly_stream=stream,
            flicker_window=self.flicker_window,
        )
        self._clock = self.clock or time.time
        self._started: float | None = None
        self._ended: float | None = None

    @property
    def recorder(self) -> ObjectiveEngineeringRecorder:
        return self._recorder

    def start(self) -> None:
        self._started = float(self._clock())
        self._ended = None

    def observe_frame(self, frame: Any) -> None:
        if self._started is None:
            self.start()
        self._recorder.observe_frame(frame)

    def run_ticks(
        self,
        ticks: Iterable[Any],
        *,
        max_samples: int | None = None,
        tick_size: float = 0.25,
        symbol: str = "MNQ",
    ) -> EngineeringSessionReport:
        """Drive LiveValidatorController; record Objective evidence each evaluate."""
        from hotirjam_ai5.live_validator.controller import LiveValidatorController
        from hotirjam_ai5.live_validator.pipeline import ArchitecturePipeline

        controller = LiveValidatorController(
            pipeline=ArchitecturePipeline(tick_size=tick_size, symbol=symbol),
            log_every_evaluation=False,
        )
        self.start()
        for tick in ticks:
            if max_samples is not None and self._recorder.sample_count >= max_samples:
                break
            frame = controller.on_tick(tick)
            self.observe_frame(frame)
        return self.finish()

    def run_live_file(
        self,
        *,
        tick_path: str | Path | None = None,
        max_samples: int | None = None,
        max_seconds: float = 3600.0,
        poll_seconds: float = 0.05,
        tick_size: float = 0.25,
        symbol: str = "MNQ",
        sleep_fn: Callable[[float], None] | None = None,
    ) -> EngineeringSessionReport:
        """Poll NT01 tick NDJSON until time or sample cap."""
        from hotirjam_ai5.live_data.ingress import LiveTickIngress
        from hotirjam_ai5.live_validator.controller import LiveValidatorController
        from hotirjam_ai5.live_validator.pipeline import ArchitecturePipeline

        sleep = sleep_fn or time.sleep
        ingress = (
            LiveTickIngress(path=tick_path, expected_symbol=symbol)
            if tick_path
            else LiveTickIngress(expected_symbol=symbol)
        )
        controller = LiveValidatorController(
            pipeline=ArchitecturePipeline(tick_size=tick_size, symbol=symbol),
            log_every_evaluation=False,
        )
        self.start()
        deadline = float(self._clock()) + max(0.0, max_seconds)

        while float(self._clock()) < deadline:
            if max_samples is not None and self._recorder.sample_count >= max_samples:
                break
            for tick in ingress.poll():
                frame = controller.on_tick(tick)
                self.observe_frame(frame)
                if max_samples is not None and self._recorder.sample_count >= max_samples:
                    break
            sleep(poll_seconds)

        return self.finish()

    def finish(self) -> EngineeringSessionReport:
        if self._started is None:
            self._started = float(self._clock())
        self._ended = float(self._clock())
        duration = max(0.0, self._ended - self._started)
        report = build_session_report(
            samples=tuple(self._recorder.samples),
            changes=tuple(self._recorder.changes),
            anomalies=tuple(self._recorder.anomalies),
            duration_seconds=duration,
            out_dir=self.out_dir,
        )
        report_path = self.out_dir / "session_report.txt"
        report_path.write_text(report.as_text() + "\n", encoding="utf-8")
        return report
