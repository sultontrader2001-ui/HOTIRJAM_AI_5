"""Live Validator controller — tick ingest → architecture snapshots."""

from __future__ import annotations

import time
from collections.abc import Callable

from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.live_validator.candle_builder import TickBarBuilder
from hotirjam_ai5.live_validator.logger import SnapshotLogger
from hotirjam_ai5.live_validator.models import ValidatorFrame
from hotirjam_ai5.live_validator.pipeline import ArchitecturePipeline
from hotirjam_ai5.live_validator.swing_confirmer import SwingConfirmer


class LiveValidatorController:
    """Observation-only controller. Never touches Decision or Execution."""

    def __init__(
        self,
        *,
        pipeline: ArchitecturePipeline | None = None,
        bar_builder: TickBarBuilder | None = None,
        swing_confirmer: SwingConfirmer | None = None,
        logger: SnapshotLogger | None = None,
        clock: Callable[[], float] | None = None,
        log_every_evaluation: bool = True,
    ) -> None:
        self._pipeline = pipeline or ArchitecturePipeline()
        self._bars = bar_builder or TickBarBuilder()
        self._swings = swing_confirmer or SwingConfirmer()
        self._logger = logger
        self._clock = clock or time.time
        self._log_every = log_every_evaluation
        self._last_price: float | None = None
        self._last_tick_ts: float | None = None
        self._latest = ArchitecturePipeline.empty_frame(timestamp=self._clock())
        self._evaluations = 0

    @property
    def latest(self) -> ValidatorFrame:
        return self._latest

    @property
    def evaluations(self) -> int:
        return self._evaluations

    def on_tick(self, tick: LiveTick) -> ValidatorFrame:
        """Ingest one live tick, update candles/swings, re-evaluate engines."""
        self._last_price = tick.last_price
        self._last_tick_ts = tick.timestamp
        newly_closed = self._bars.on_tick(tick)
        if newly_closed:
            self._swings.on_closed_candles(newly_closed)
        return self._evaluate()

    def evaluate_now(self) -> ValidatorFrame:
        """Force an evaluation from current buffers (e.g. on display refresh)."""
        if self._last_price is None:
            self._latest = ArchitecturePipeline.empty_frame(timestamp=self._clock())
            return self._latest
        return self._evaluate()

    def _evaluate(self) -> ValidatorFrame:
        assert self._last_price is not None
        ts = self._last_tick_ts if self._last_tick_ts is not None else self._clock()
        frame = self._pipeline.evaluate(
            current_price=self._last_price,
            timestamp=ts,
            candles=self._bars.candles_for_engines(),
            confirmed_highs=self._swings.confirmed_highs,
            confirmed_lows=self._swings.confirmed_lows,
        )
        self._latest = frame
        self._evaluations += 1
        if self._logger is not None and self._log_every:
            self._logger.log(frame)
        return frame
