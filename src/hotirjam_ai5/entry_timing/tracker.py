"""Entry Timing Auditor — observes internal signals; analytics only.

Does not belong to Trade Decision. Never connects to a broker or changes
thresholds. Tracks post-entry price path for 5 minutes.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
import time
import uuid

from hotirjam_ai5.entry_timing.classify import classify_timing, signed_points
from hotirjam_ai5.entry_timing.log import TimingLogWriter
from hotirjam_ai5.entry_timing.models import (
    CHECKPOINT_SECONDS,
    TIMING_WINDOW_SECONDS,
    CheckpointSample,
    TimingClass,
    TimingRecord,
    TimingSummary,
    _OpenTimingPath,
)
from hotirjam_ai5.trade_decision.models import TradeDecision, TradeDecisionSnapshot

_INTERNAL = frozenset(
    {TradeDecision.BUY_INTERNAL.value, TradeDecision.SELL_INTERNAL.value}
)


class EntryTimingAuditor:
    """Edge-triggered entry timing audit for BUY_INTERNAL / SELL_INTERNAL."""

    def __init__(
        self,
        *,
        log_writer: TimingLogWriter | None = None,
        clock: Callable[[], float] | None = None,
        id_factory: Callable[[], str] | None = None,
        window_seconds: float = TIMING_WINDOW_SECONDS,
        checkpoints: Sequence[int] = CHECKPOINT_SECONDS,
    ) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._log = log_writer or TimingLogWriter()
        self._clock = clock or time.time
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)
        self._window = window_seconds
        self._checkpoints = tuple(sorted(checkpoints))
        self._open: list[_OpenTimingPath] = []
        self._completed: list[TimingRecord] = []
        self._last_observed_decision: str | None = None

    @property
    def completed(self) -> tuple[TimingRecord, ...]:
        return tuple(self._completed)

    @property
    def pending_count(self) -> int:
        return len(self._open)

    def observe(
        self,
        decision: TradeDecisionSnapshot,
        *,
        current_price: float | None,
        timestamp: float | None = None,
        symbol: str = "MNQ",
    ) -> TimingRecord | None:
        """Open a new timing path on decision edge; always update open paths."""
        now = timestamp if timestamp is not None else self._clock()
        decision_value = decision.decision.value
        opened: TimingRecord | None = None

        if (
            decision_value in _INTERNAL
            and decision_value != self._last_observed_decision
            and current_price is not None
        ):
            path = _OpenTimingPath(
                signal_id=self._id_factory(),
                symbol=symbol,
                decision=decision_value,
                entry_price=current_price,
                entry_time=now,
            )
            path.samples.append((now, current_price))
            self._open.append(path)
            opened = TimingRecord(
                signal_id=path.signal_id,
                symbol=path.symbol,
                decision=path.decision,
                entry_price=path.entry_price,
                entry_time=path.entry_time,
            )

        self._last_observed_decision = decision_value
        self.update_price(current_price=current_price, timestamp=now)
        return opened

    def update_price(
        self,
        *,
        current_price: float | None,
        timestamp: float | None = None,
    ) -> list[TimingRecord]:
        """Advance open paths with the latest price; finalize expired windows."""
        if current_price is None:
            return []
        now = timestamp if timestamp is not None else self._clock()
        still_open: list[_OpenTimingPath] = []
        finished: list[TimingRecord] = []

        for path in self._open:
            age = now - path.entry_time
            points = signed_points(
                decision=path.decision,
                entry_price=path.entry_price,
                current_price=current_price,
            )
            path.samples.append((now, current_price))
            path.mfe = max(path.mfe, points)
            path.mae = min(path.mae, points)

            for offset in self._checkpoints:
                if offset in path.captured_offsets:
                    continue
                if age + 1e-9 >= offset:
                    path.checkpoints.append(
                        CheckpointSample(
                            offset_seconds=offset,
                            price=current_price,
                            points=points,
                        )
                    )
                    path.captured_offsets.add(offset)

            if age + 1e-9 >= self._window:
                record = self._finalize(path, exit_price=current_price, exit_time=now)
                self._log.write_completed(record)
                self._completed.append(record)
                finished.append(record)
            else:
                still_open.append(path)

        self._open = still_open
        return finished

    def summary(self) -> TimingSummary:
        """Aggregate statistics over completed timing audits."""
        records = [r for r in self._completed if r.mfe is not None and r.mae is not None]
        if not records:
            return TimingSummary()

        def avg_at(offset: int) -> float:
            values = [
                c.points
                for r in records
                for c in r.checkpoints
                if c.offset_seconds == offset
            ]
            return sum(values) / len(values) if values else 0.0

        return TimingSummary(
            signal_count=len(records),
            early_count=sum(1 for r in records if r.timing_class is TimingClass.EARLY),
            normal_count=sum(1 for r in records if r.timing_class is TimingClass.NORMAL),
            late_count=sum(1 for r in records if r.timing_class is TimingClass.LATE),
            inconclusive_count=sum(
                1 for r in records if r.timing_class is TimingClass.INCONCLUSIVE
            ),
            average_mfe=sum(r.mfe for r in records if r.mfe is not None) / len(records),
            average_mae=sum(r.mae for r in records if r.mae is not None) / len(records),
            average_points_30s=avg_at(30),
            average_points_1m=avg_at(60),
            average_points_2m=avg_at(120),
            average_points_3m=avg_at(180),
            average_points_5m=avg_at(300),
        )

    def format_record(self, record: TimingRecord) -> str:
        """Human-readable timing report block for one signal."""
        lines = [
            f"Signal     {record.decision}",
            f"Entry      {record.entry_price}",
        ]
        labels = {
            30: "30 sec",
            60: "1 min",
            120: "2 min",
            180: "3 min",
            300: "5 min",
        }
        by_offset = {c.offset_seconds: c for c in record.checkpoints}
        for offset in self._checkpoints:
            sample = by_offset.get(offset)
            label = labels.get(offset, f"{offset}s")
            if sample is None:
                lines.append(f"{label:<10} —")
            else:
                lines.append(f"{label:<10}{sample.points:+.2f}")
        mfe = "—" if record.mfe is None else f"{record.mfe:+.2f}"
        mae = "—" if record.mae is None else f"{record.mae:+.2f}"
        lines.append(f"MFE        {mfe}")
        lines.append(f"MAE        {mae}")
        lines.append(f"Class      {record.timing_class.value}")
        lines.append(f"Reason     {record.classification_reason}")
        return "\n".join(lines)

    def format_report(self) -> str:
        """Full timing report: per-signal blocks + performance summary."""
        blocks = [self.format_record(record) for record in self._completed]
        summary = self.summary()
        summary_block = "\n".join(
            [
                "PERFORMANCE SUMMARY",
                f"Signals           {summary.signal_count}",
                f"EARLY             {summary.early_count}",
                f"NORMAL            {summary.normal_count}",
                f"LATE              {summary.late_count}",
                f"INCONCLUSIVE      {summary.inconclusive_count}",
                f"Average MFE       {summary.average_mfe:+.2f}",
                f"Average MAE       {summary.average_mae:+.2f}",
                f"Avg move 30 sec   {summary.average_points_30s:+.2f}",
                f"Avg move 1 min    {summary.average_points_1m:+.2f}",
                f"Avg move 2 min    {summary.average_points_2m:+.2f}",
                f"Avg move 3 min    {summary.average_points_3m:+.2f}",
                f"Avg move 5 min    {summary.average_points_5m:+.2f}",
            ]
        )
        if not blocks:
            return summary_block
        return "\n\n".join(blocks) + "\n\n" + summary_block

    def _finalize(
        self,
        path: _OpenTimingPath,
        *,
        exit_price: float,
        exit_time: float,
    ) -> TimingRecord:
        checkpoints = tuple(
            sorted(path.checkpoints, key=lambda item: item.offset_seconds)
        )
        timing_class, reason = classify_timing(
            mfe=path.mfe,
            mae=path.mae,
            checkpoints=checkpoints,
        )
        return TimingRecord(
            signal_id=path.signal_id,
            symbol=path.symbol,
            decision=path.decision,
            entry_price=path.entry_price,
            entry_time=path.entry_time,
            checkpoints=checkpoints,
            mfe=path.mfe,
            mae=path.mae,
            timing_class=timing_class,
            classification_reason=reason,
            exit_price=exit_price,
            exit_time=exit_time,
        )
