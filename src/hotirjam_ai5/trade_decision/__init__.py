"""Trade Decision Engine (Sprint 15+) — orchestrator with internal policy."""

from hotirjam_ai5.trade_decision.engine import (
    TradeDecisionEngine,
    evaluate_trade_decision,
)
from hotirjam_ai5.trade_decision.models import (
    BuyConfidenceBreakdown,
    BuyScoreBreakdown,
    DecisionExplanation,
    ExplanationStatus,
    SignalStability,
    TradeDecision,
    TradeDecisionSnapshot,
)
from hotirjam_ai5.trade_decision.policy import (
    TradeAuthorization,
    apply_trade_decision_policy,
    build_decision_explanation,
    compute_buy_confidence,
    compute_buy_score,
    format_buy_score_reason,
    is_buy_eligible,
    matches_buy_strategy,
    qualifies_for_signal_stability,
    resolve_signal_stability,
    resolve_trade_authorization,
    signal_stability_explanation_status,
)

__all__ = [
    "BuyConfidenceBreakdown",
    "BuyScoreBreakdown",
    "DecisionExplanation",
    "ExplanationStatus",
    "SignalStability",
    "TradeAuthorization",
    "TradeDecision",
    "TradeDecisionEngine",
    "TradeDecisionSnapshot",
    "apply_trade_decision_policy",
    "build_decision_explanation",
    "compute_buy_confidence",
    "compute_buy_score",
    "evaluate_trade_decision",
    "format_buy_score_reason",
    "is_buy_eligible",
    "matches_buy_strategy",
    "qualifies_for_signal_stability",
    "resolve_signal_stability",
    "resolve_trade_authorization",
    "signal_stability_explanation_status",
]
