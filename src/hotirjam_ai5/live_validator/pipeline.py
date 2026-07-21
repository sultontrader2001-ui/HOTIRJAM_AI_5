"""Architecture pipeline: Objective → Initiative → Response → Continuation → Break.

Observation only. Decision and execution are never invoked.
"""

from __future__ import annotations

from hotirjam_ai5.break_capability import (
    BreakCapabilityInputs,
    BreakCapabilitySnapshot,
    evaluate_break_capability,
)
from hotirjam_ai5.continuation import (
    ContinuationInputs,
    ContinuationSnapshot,
    evaluate_continuation,
)
from hotirjam_ai5.initiative import (
    InitiativeInputs,
    InitiativeSnapshot,
    OhlcCandle,
    evaluate_initiative,
)
from hotirjam_ai5.live_validator.models import ValidatorFrame
from hotirjam_ai5.objective import (
    ConfirmedSwing,
    ObjectiveInputs,
    ObjectiveSnapshot,
    evaluate_objectives,
)
from hotirjam_ai5.response import (
    ResponseInputs,
    ResponseSnapshot,
    evaluate_response,
)


class ArchitecturePipeline:
    """Run the five frozen architecture engines for one observation frame."""

    def __init__(self, *, tick_size: float = 0.25, symbol: str = "MNQ") -> None:
        if tick_size <= 0.0:
            raise ValueError("tick_size must be positive")
        self._tick_size = tick_size
        self._symbol = symbol

    @property
    def tick_size(self) -> float:
        return self._tick_size

    def evaluate(
        self,
        *,
        current_price: float,
        timestamp: float,
        candles: tuple[OhlcCandle, ...],
        confirmed_highs: tuple[ConfirmedSwing, ...],
        confirmed_lows: tuple[ConfirmedSwing, ...],
    ) -> ValidatorFrame:
        """Evaluate the full observation chain. Never calls Decision/Execution."""
        objective = evaluate_objectives(
            ObjectiveInputs(
                current_price=current_price,
                tick_size=self._tick_size,
                confirmed_highs=confirmed_highs,
                confirmed_lows=confirmed_lows,
                timestamp=timestamp,
            )
        )
        initiative = evaluate_initiative(
            InitiativeInputs(
                objectives=objective,
                candles=candles,
                tick_size=self._tick_size,
                timestamp=timestamp,
            )
        )
        response = evaluate_response(
            ResponseInputs(
                objectives=objective,
                initiative=initiative,
                candles=candles,
                tick_size=self._tick_size,
                timestamp=timestamp,
            )
        )
        continuation = evaluate_continuation(
            ContinuationInputs(
                objectives=objective,
                initiative=initiative,
                response=response,
                candles=candles,
                tick_size=self._tick_size,
                timestamp=timestamp,
            )
        )
        break_capability = evaluate_break_capability(
            BreakCapabilityInputs(
                objectives=objective,
                initiative=initiative,
                response=response,
                continuation=continuation,
                timestamp=timestamp,
            )
        )
        return ValidatorFrame(
            timestamp=timestamp,
            current_price=current_price,
            symbol=self._symbol,
            candle_count=len(candles),
            swing_high_count=len(confirmed_highs),
            swing_low_count=len(confirmed_lows),
            objective=objective,
            initiative=initiative,
            response=response,
            continuation=continuation,
            break_capability=break_capability,
            decision="DISABLED",
        )

    @staticmethod
    def empty_frame(*, timestamp: float, symbol: str = "MNQ") -> ValidatorFrame:
        """Frame when no price is available yet."""
        return ValidatorFrame(
            timestamp=timestamp,
            current_price=None,
            symbol=symbol,
            candle_count=0,
            swing_high_count=0,
            swing_low_count=0,
            objective=ObjectiveSnapshot.empty(timestamp=timestamp),
            initiative=InitiativeSnapshot.empty(timestamp=timestamp),
            response=ResponseSnapshot.empty(timestamp=timestamp),
            continuation=ContinuationSnapshot.empty(timestamp=timestamp),
            break_capability=BreakCapabilitySnapshot.empty(timestamp=timestamp),
            decision="DISABLED",
        )
