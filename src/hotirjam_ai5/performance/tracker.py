"""Performance Tracker — observes internal signals; analytics only.

Does not belong to Trade Decision. Never connects to a broker, creates
orders, or modifies decision logic.
"""

from __future__ import annotations

from collections.abc import Callable
import time
import uuid

from hotirjam_ai5.liquidity import LiquiditySnapshot
from hotirjam_ai5.market_context import MarketContextSnapshot
from hotirjam_ai5.performance.log import PerformanceLogWriter
from hotirjam_ai5.performance.models import (
    LiquidityEvidence,
    PerformanceSnapshot,
    PhysicsEvidence,
    SignalRecord,
    SignalResult,
)
from hotirjam_ai5.performance.timezones import format_multi_zone
from hotirjam_ai5.physics.measurements import PhysicsSnapshot
from hotirjam_ai5.trade_decision.models import TradeDecision, TradeDecisionSnapshot

DEFAULT_EVALUATION_DELAY_SECONDS = 300.0
_INTERNAL_DECISIONS = frozenset(
    {TradeDecision.BUY_INTERNAL.value, TradeDecision.SELL_INTERNAL.value}
)


class PerformanceTracker:
    """Records BUY_INTERNAL / SELL_INTERNAL and evaluates them after a delay.

    Observation is edge-triggered: a new open signal is stored only when the
    decision transitions into BUY_INTERNAL or SELL_INTERNAL. Continuous
    READY refreshes do not create duplicate records. Pending signals are
    evaluated once the evaluation delay elapses and a market price is available.
    """

    def __init__(
        self,
        *,
        evaluation_delay_seconds: float = DEFAULT_EVALUATION_DELAY_SECONDS,
        log_writer: PerformanceLogWriter | None = None,
        clock: Callable[[], float] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        if evaluation_delay_seconds <= 0:
            raise ValueError("evaluation_delay_seconds must be positive")
        self._delay = evaluation_delay_seconds
        self._log = log_writer or PerformanceLogWriter()
        self._clock = clock or time.time
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)
        self._records: list[SignalRecord] = []
        self._last_observed_decision: str | None = None

    @property
    def records(self) -> tuple[SignalRecord, ...]:
        return tuple(self._records)

    def observe(
        self,
        decision: TradeDecisionSnapshot,
        *,
        symbol: str,
        current_price: float | None,
        market_context: MarketContextSnapshot,
        physics: PhysicsSnapshot,
        liquidity: LiquiditySnapshot | None,
        timestamp: float | None = None,
    ) -> SignalRecord | None:
        """Observe one Trade Decision snapshot.

        Records a signal when decision becomes BUY_INTERNAL or SELL_INTERNAL.
        Always advances pending evaluations when a price is available.
        """
        now = timestamp if timestamp is not None else self._clock()
        decision_value = decision.decision.value

        recorded: SignalRecord | None = None
        if (
            decision_value in _INTERNAL_DECISIONS
            and decision_value != self._last_observed_decision
            and current_price is not None
        ):
            recorded = self._open_signal(
                decision,
                symbol=symbol,
                entry_price=current_price,
                market_context=market_context,
                physics=physics,
                liquidity=liquidity,
                timestamp=now,
            )
            self._records.append(recorded)

        self._last_observed_decision = decision_value
        self.evaluate_pending(current_price=current_price, timestamp=now)
        return recorded

    def evaluate_pending(
        self,
        *,
        current_price: float | None,
        timestamp: float | None = None,
    ) -> list[SignalRecord]:
        """Evaluate pending signals whose delay has elapsed."""
        if current_price is None:
            return []
        now = timestamp if timestamp is not None else self._clock()
        completed: list[SignalRecord] = []
        updated: list[SignalRecord] = []
        for record in self._records:
            if record.result is not SignalResult.PENDING:
                updated.append(record)
                continue
            age = now - record.entry_time.epoch_seconds
            if age < self._delay:
                updated.append(record)
                continue
            finished = self._evaluate(record, exit_price=current_price, timestamp=now)
            self._log.write_completed(finished)
            completed.append(finished)
            updated.append(finished)
        self._records = updated
        return completed

    def snapshot(self) -> PerformanceSnapshot:
        """Build immutable PERFORMANCE stats for the dashboard."""
        buy = sum(1 for r in self._records if r.decision == TradeDecision.BUY_INTERNAL.value)
        sell = sum(1 for r in self._records if r.decision == TradeDecision.SELL_INTERNAL.value)
        success = sum(1 for r in self._records if r.result is SignalResult.SUCCESS)
        failed = sum(1 for r in self._records if r.result is SignalResult.FAILED)
        neutral = sum(1 for r in self._records if r.result is SignalResult.NEUTRAL)
        pending = sum(1 for r in self._records if r.result is SignalResult.PENDING)
        completed = [r for r in self._records if r.points is not None]
        if completed:
            average = sum(r.points for r in completed if r.points is not None) / len(completed)
            evaluated = success + failed + neutral
            win_rate = (success / evaluated) * 100.0 if evaluated else 0.0
        else:
            average = 0.0
            win_rate = 0.0
        last = self._records[-1] if self._records else None
        if last is None:
            return PerformanceSnapshot(
                buy_signals=buy,
                sell_signals=sell,
                success_count=success,
                failed_count=failed,
                neutral_count=neutral,
                pending_count=pending,
            )
        return PerformanceSnapshot(
            buy_signals=buy,
            sell_signals=sell,
            success_count=success,
            failed_count=failed,
            neutral_count=neutral,
            pending_count=pending,
            win_rate=win_rate,
            average_points=average,
            last_signal_decision=last.decision,
            last_signal_utc=last.entry_time.utc,
            last_signal_new_york=last.entry_time.new_york,
            last_signal_tashkent=last.entry_time.tashkent,
        )

    def _open_signal(
        self,
        decision: TradeDecisionSnapshot,
        *,
        symbol: str,
        entry_price: float,
        market_context: MarketContextSnapshot,
        physics: PhysicsSnapshot,
        liquidity: LiquiditySnapshot | None,
        timestamp: float,
    ) -> SignalRecord:
        shift = getattr(liquidity, "liquidity_shift", "UNKNOWN")
        imbalance = getattr(liquidity, "dom_imbalance", "UNKNOWN")
        return SignalRecord(
            signal_id=self._id_factory(),
            symbol=symbol,
            decision=decision.decision.value,
            entry_price=entry_price,
            buy_score=decision.buy_score,
            sell_score=decision.sell_score,
            buy_confidence=decision.buy_confidence,
            sell_confidence=decision.sell_confidence,
            market_state=market_context.state,
            behavior=market_context.behavior,
            physics=PhysicsEvidence(
                velocity=physics.tick_velocity,
                acceleration=physics.tick_acceleration,
            ),
            liquidity=LiquidityEvidence(shift=str(shift), imbalance=str(imbalance)),
            entry_time=format_multi_zone(timestamp),
        )

    @staticmethod
    def _evaluate(
        record: SignalRecord,
        *,
        exit_price: float,
        timestamp: float,
    ) -> SignalRecord:
        if record.decision == TradeDecision.BUY_INTERNAL.value:
            points = exit_price - record.entry_price
        elif record.decision == TradeDecision.SELL_INTERNAL.value:
            points = record.entry_price - exit_price
        else:
            raise ValueError(f"unsupported decision for evaluation: {record.decision}")
        if points > 0:
            result = SignalResult.SUCCESS
        elif points < 0:
            result = SignalResult.FAILED
        else:
            result = SignalResult.NEUTRAL
        return SignalRecord(
            signal_id=record.signal_id,
            symbol=record.symbol,
            decision=record.decision,
            entry_price=record.entry_price,
            buy_score=record.buy_score,
            sell_score=record.sell_score,
            buy_confidence=record.buy_confidence,
            sell_confidence=record.sell_confidence,
            market_state=record.market_state,
            behavior=record.behavior,
            physics=record.physics,
            liquidity=record.liquidity,
            entry_time=record.entry_time,
            result=result,
            exit_price=exit_price,
            points=points,
            evaluation_time=format_multi_zone(timestamp),
        )
