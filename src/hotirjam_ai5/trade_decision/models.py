"""Trade decision models.

Trade Decision Engine output values. BUY_INTERNAL and SELL_INTERNAL are
observation-only. Tradable BUY and SELL remain unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TradeDecision(StrEnum):
    """Observation-only trade decision output."""

    NO_TRADE = "NO_TRADE"
    BUY_INTERNAL = "BUY_INTERNAL"
    SELL_INTERNAL = "SELL_INTERNAL"


class ExplanationStatus(StrEnum):
    """Per-category explanation status for a trade decision."""

    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class SignalStability(StrEnum):
    """Temporal confirmation across consecutive evaluations."""

    STABLE = "STABLE"
    UNSTABLE = "UNSTABLE"


class DecisionReadiness(StrEnum):
    """Final readiness of a directional pipeline for signal activation."""

    READY = "READY"
    NOT_READY = "NOT_READY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class BuyScoreBreakdown:
    """Per-category BUY score contributions (setup quality, max 100)."""

    assessment: int
    feed_health: int
    market_state: int
    behavior: int
    physics: int
    liquidity: int

    @property
    def total(self) -> int:
        return (
            self.assessment
            + self.feed_health
            + self.market_state
            + self.behavior
            + self.physics
            + self.liquidity
        )


@dataclass(frozen=True, slots=True)
class BuyConfidenceBreakdown:
    """Per-category BUY confidence contributions (decision reliability, max 100)."""

    assessment_reliability: int
    feed_reliability: int
    physics_stability: int
    liquidity_reliability: int
    market_stability: int

    @property
    def total(self) -> int:
        return (
            self.assessment_reliability
            + self.feed_reliability
            + self.physics_stability
            + self.liquidity_reliability
            + self.market_stability
        )


# SELL uses identical category layouts with mirrored directional rules.
SellScoreBreakdown = BuyScoreBreakdown
SellConfidenceBreakdown = BuyConfidenceBreakdown


@dataclass(frozen=True, slots=True)
class DecisionExplanation:
    """Structured WHY for the current trade decision."""

    assessment: ExplanationStatus
    feed: ExplanationStatus
    market_state: ExplanationStatus
    behavior: ExplanationStatus
    physics: ExplanationStatus
    liquidity: ExplanationStatus
    signal_stability: ExplanationStatus
    readiness: ExplanationStatus
    summary: str


@dataclass(frozen=True, slots=True)
class ScoreContributionLine:
    """One category contribution from a real score breakdown."""

    label: str
    points: int


@dataclass(frozen=True, slots=True)
class DecisionScoreEvidence:
    """Raw inputs that produced the score breakdowns (Sprint 38).

    Captured once at decision time — explainability never re-derives scores.
    """

    assessment_state: str
    feed_status: str
    feed_latency_ms: float | None
    market_state: str
    state_direction: str
    behavior: str
    behavior_direction: str
    tick_velocity: float | None
    tick_acceleration: float | None
    liquidity_shift: str | None
    dom_imbalance: str | None


@dataclass(frozen=True, slots=True)
class DecisionExplainability:
    """Fully explainable view of one trade decision (Sprint 36/38)."""

    headline: str
    buy_contributions: tuple[ScoreContributionLine, ...]
    buy_total: int
    sell_contributions: tuple[ScoreContributionLine, ...]
    sell_total: int
    checklist: tuple[str, ...]
    selection_lines: tuple[str, ...]
    # Sprint 38 — detailed reasoning blocks + final reason sentences.
    buy_detail_lines: tuple[str, ...] = ()
    sell_detail_lines: tuple[str, ...] = ()
    buy_reason: str = ""
    sell_reason: str = ""
    evidence: DecisionScoreEvidence | None = None


@dataclass(frozen=True, slots=True)
class MemoryScoreInfluence:
    """Logged Memory adjustment applied to primary BUY/SELL scores (Sprint 44)."""

    original_buy_score: int
    original_sell_score: int
    buy_delta: int
    sell_delta: int
    adjusted_buy_score: int
    adjusted_sell_score: int
    consensus: str
    agreement: float
    persistence: float
    confidence: float
    status: str
    influence_pct: float
    applied: bool

    @staticmethod
    def none(original_buy: int, original_sell: int) -> MemoryScoreInfluence:
        """Zero adjustment when Memory is unavailable or uncertain."""
        return MemoryScoreInfluence(
            original_buy_score=original_buy,
            original_sell_score=original_sell,
            buy_delta=0,
            sell_delta=0,
            adjusted_buy_score=original_buy,
            adjusted_sell_score=original_sell,
            consensus="NEUTRAL",
            agreement=0.0,
            persistence=0.0,
            confidence=0.0,
            status="UNCERTAIN",
            influence_pct=0.0,
            applied=False,
        )


@dataclass(frozen=True, slots=True)
class TradeDecisionSnapshot:
    """Trade decision derived from assessment, context, physics, and liquidity."""

    timestamp: float
    decision: TradeDecision
    reason: str
    next_action: str
    buy_score: int = 0
    buy_confidence: int = 0
    sell_score: int = 0
    sell_confidence: int = 0
    signal_stability: SignalStability = SignalStability.UNSTABLE
    sell_signal_stability: SignalStability = SignalStability.UNSTABLE
    decision_readiness: DecisionReadiness = DecisionReadiness.UNKNOWN
    sell_decision_readiness: DecisionReadiness = DecisionReadiness.UNKNOWN
    decision_explanation: DecisionExplanation | None = None
    buy_score_breakdown: BuyScoreBreakdown | None = None
    sell_score_breakdown: SellScoreBreakdown | None = None
    explainability: DecisionExplainability | None = None
    # Sprint 44 — Memory secondary score influence (never invents decisions).
    memory_influence: MemoryScoreInfluence | None = None
