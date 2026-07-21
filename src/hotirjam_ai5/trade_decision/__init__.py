"""Trade Decision Engine (Sprint 15+) — orchestrator with internal policy."""

from hotirjam_ai5.trade_decision.engine import (
    TradeDecisionEngine,
    evaluate_trade_decision,
)
from hotirjam_ai5.trade_decision.models import (
    BuyScoreBreakdown,
    TradeDecision,
    TradeDecisionSnapshot,
)
from hotirjam_ai5.trade_decision.policy import (
    TradeAuthorization,
    apply_trade_decision_policy,
    compute_buy_score,
    format_buy_score_reason,
    is_buy_eligible,
    matches_buy_strategy,
    resolve_trade_authorization,
)

__all__ = [
    "BuyScoreBreakdown",
    "TradeAuthorization",
    "TradeDecision",
    "TradeDecisionEngine",
    "TradeDecisionSnapshot",
    "apply_trade_decision_policy",
    "compute_buy_score",
    "evaluate_trade_decision",
    "format_buy_score_reason",
    "is_buy_eligible",
    "matches_buy_strategy",
    "resolve_trade_authorization",
]
