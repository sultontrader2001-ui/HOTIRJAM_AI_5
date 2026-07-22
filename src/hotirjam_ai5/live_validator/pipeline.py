"""Architecture pipeline: Objective → Initiative → Response → Continuation → Break.

Observation only. Decision and execution are never invoked.
"""

from __future__ import annotations

from pathlib import Path

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
    InitiativeEngine,
    InitiativeInputs,
    InitiativeSnapshot,
    OhlcCandle,
)
from hotirjam_ai5.live_validator.models import ValidatorFrame
from hotirjam_ai5.live_validator.diagnostic_projection import derive_diagnostic_log
from hotirjam_ai5.objective import (
    ConfirmedSwing,
    ObjectiveEngine,
    ObjectiveInputs,
    ObjectiveSnapshot,
)
from hotirjam_ai5.objective_diagnostics import (
    ObjectiveAuditReport,
    ObjectiveDiagnosticsInputs,
    PersistentStructuralHierarchy,
    audit_objectives,
    use_structural_hierarchy,
)
from hotirjam_ai5.response import (
    ResponseInputs,
    ResponseSnapshot,
    evaluate_response,
)


class ArchitecturePipeline:
    """Run the five frozen architecture engines for one observation frame."""

    def __init__(
        self,
        *,
        tick_size: float = 0.25,
        symbol: str = "MNQ",
        hierarchy_checkpoint_path: Path | None = None,
        structural_hierarchy: PersistentStructuralHierarchy | None = None,
        initiative_checkpoint_path: Path | None = None,
        initiative_engine: InitiativeEngine | None = None,
    ) -> None:
        if tick_size <= 0.0:
            raise ValueError("tick_size must be positive")
        self._tick_size = tick_size
        self._symbol = symbol
        self._objective_engine = ObjectiveEngine()
        self._structural_hierarchy = structural_hierarchy or PersistentStructuralHierarchy(
            checkpoint_path=hierarchy_checkpoint_path
        )
        self._initiative_engine = initiative_engine or InitiativeEngine(
            checkpoint_path=initiative_checkpoint_path
        )

    @property
    def tick_size(self) -> float:
        return self._tick_size

    @property
    def structural_hierarchy(self) -> PersistentStructuralHierarchy:
        return self._structural_hierarchy

    @property
    def initiative_engine(self) -> InitiativeEngine:
        return self._initiative_engine

    @property
    def objective_engine(self) -> ObjectiveEngine:
        return self._objective_engine

    def audit_objectives(
        self, inputs: ObjectiveDiagnosticsInputs
    ) -> ObjectiveAuditReport:
        """Render diagnostics from the same hierarchy consumed by Objective.

        Prefer ``ObjectiveEngine.last_audit_report`` on the live path (H-6.8.2).
        This method remains for isolated diagnostics / tests only.
        """
        with use_structural_hierarchy(self._structural_hierarchy):
            return audit_objectives(inputs)

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
        with use_structural_hierarchy(self._structural_hierarchy):
            objective = self._objective_engine.evaluate(
                ObjectiveInputs(
                    current_price=current_price,
                    tick_size=self._tick_size,
                    confirmed_highs=confirmed_highs,
                    confirmed_lows=confirmed_lows,
                    timestamp=timestamp,
                )
            )
            # H-6.8.2: reuse the exact report Objective just consumed — no second
            # hierarchy.evaluate() for presentation.
            diagnostics = self._objective_engine.last_audit_report
        initiative = self._initiative_engine.evaluate(
            InitiativeInputs(
                candles=candles,
                tick_size=self._tick_size,
                timestamp=timestamp,
                objectives=objective,
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
        # H-6.9.4: exactly one pure derive R→P per tick (after engines use R only).
        diagnostic_log = derive_diagnostic_log(diagnostics, objective)
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
            objective_diagnostics=diagnostics,
            diagnostic_log=diagnostic_log,
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
