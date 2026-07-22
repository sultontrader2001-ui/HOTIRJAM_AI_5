"""Live Validator models — observation-only architecture pipeline state."""

from __future__ import annotations

from dataclasses import dataclass

from hotirjam_ai5.break_capability import BreakCapabilitySnapshot
from hotirjam_ai5.continuation import ContinuationSnapshot
from hotirjam_ai5.initiative import InitiativeSnapshot
from hotirjam_ai5.live_validator.diagnostic_projection import DiagnosticLogProjection
from hotirjam_ai5.objective import ObjectiveSnapshot
from hotirjam_ai5.objective_diagnostics import ObjectiveAuditReport
from hotirjam_ai5.response import ResponseSnapshot


@dataclass(frozen=True, slots=True)
class ValidatorFrame:
    """One observation frame from the live architecture pipeline.

    Decision and execution are always disabled in this frame.

    H-6.9.4 Alternative E:
    - ``objective_diagnostics`` (R): runtime ObjectiveAuditReport — selection / IDC detail
    - ``diagnostic_log`` (P): compact projection — Snapshot Logger / IDC summary
    """

    timestamp: float
    current_price: float | None
    symbol: str
    candle_count: int
    swing_high_count: int
    swing_low_count: int
    objective: ObjectiveSnapshot
    initiative: InitiativeSnapshot
    response: ResponseSnapshot
    continuation: ContinuationSnapshot
    break_capability: BreakCapabilitySnapshot
    decision: str = "DISABLED"
    objective_diagnostics: ObjectiveAuditReport | None = None
    diagnostic_log: DiagnosticLogProjection | None = None
