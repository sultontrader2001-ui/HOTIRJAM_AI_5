"""Unit tests for Trade Decision Policy — BUY Scoring Framework (Sprint 24)."""

from __future__ import annotations

from hotirjam_ai5.decision_assessment import (
    DecisionAssessmentSnapshot,
    DecisionAssessmentState,
)
from hotirjam_ai5.liquidity import LiquidityBias, LiquiditySnapshot
from hotirjam_ai5.market_context import MarketContextSnapshot
from hotirjam_ai5.physics.measurements import PhysicsSnapshot
from hotirjam_ai5.trade_decision import (
    TradeDecision,
    TradeDecisionEngine,
    apply_trade_decision_policy,
    compute_buy_score,
    evaluate_trade_decision,
    is_buy_eligible,
)
from hotirjam_ai5.trade_decision.policy import (
    NEXT_ACTION,
    POINTS_ASSESSMENT,
    POINTS_BEHAVIOR,
    POINTS_FEED_HEALTH,
    POINTS_LIQUIDITY,
    POINTS_MARKET_STATE,
    POINTS_PHYSICS,
    POINTS_TOTAL,
    format_buy_score_reason,
)


def _assessment(state: DecisionAssessmentState) -> DecisionAssessmentSnapshot:
    return DecisionAssessmentSnapshot(
        timestamp=100.0,
        assessment_state=state,
        assessment_ready=state is DecisionAssessmentState.READY,
        reason="Assessment workflow observation",
        next_stage="Assessment workflow next stage",
    )


def _context(
    *,
    state: str = "ACTIVE",
    behavior: str = "STABLE",
    feed_status: str = "HEALTHY",
) -> MarketContextSnapshot:
    return MarketContextSnapshot(
        timestamp=100.0,
        state=state,
        state_reason="Structured field fixture",
        transition="NONE",
        transition_changed=False,
        transition_duration=12.0,
        behavior=behavior,
        behavior_reason="Structured field fixture",
        feed_status=feed_status,
        feed_quality="GOOD",
        dom_status="HEALTHY",
        dom_quality="GOOD",
        tick_rate=8.0,
        spread=0.25,
        summary="ACTIVE market with STABLE behavior.",
    )


def _physics(
    *,
    velocity: float | None = 1.0,
    acceleration: float | None = 0.2,
) -> PhysicsSnapshot:
    return PhysicsSnapshot(
        spread=0.25,
        mid_price=20100.0,
        tick_velocity=velocity,
        tick_acceleration=acceleration,
        tick_count=50,
    )


def _liquidity(
    *,
    liquidity_shift: str = LiquidityBias.BUY.value,
    dom_imbalance: str = LiquidityBias.BUY.value,
) -> LiquiditySnapshot:
    return LiquiditySnapshot(
        timestamp=100.0,
        liquidity_shift=liquidity_shift,
        dom_imbalance=dom_imbalance,
    )


def test_full_score_is_100_but_still_no_trade() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    breakdown = compute_buy_score(
        assessment, _context(), _physics(), _liquidity()
    )
    assert breakdown.assessment == POINTS_ASSESSMENT
    assert breakdown.feed_health == POINTS_FEED_HEALTH
    assert breakdown.market_state == POINTS_MARKET_STATE
    assert breakdown.behavior == POINTS_BEHAVIOR
    assert breakdown.physics == POINTS_PHYSICS
    assert breakdown.liquidity == POINTS_LIQUIDITY
    assert breakdown.total == POINTS_TOTAL
    assert is_buy_eligible(assessment, _context(), _physics(), _liquidity()) is True

    snap = apply_trade_decision_policy(
        assessment, _context(), _physics(), _liquidity(), timestamp=1.0
    )
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.decision is not TradeDecision.BUY
    assert snap.buy_score == 100
    assert snap.reason == "BUY score: 100/100. Awaiting release."
    assert snap.next_action == NEXT_ACTION


def test_assessment_category_points() -> None:
    ready = compute_buy_score(
        _assessment(DecisionAssessmentState.READY), None, None, None
    )
    blocked = compute_buy_score(
        _assessment(DecisionAssessmentState.BLOCKED), None, None, None
    )
    assert ready.assessment == POINTS_ASSESSMENT
    assert ready.total == POINTS_ASSESSMENT
    assert blocked.assessment == 0
    assert blocked.total == 0


def test_feed_health_category_points() -> None:
    assessment = _assessment(DecisionAssessmentState.BLOCKED)
    healthy = compute_buy_score(assessment, _context(feed_status="HEALTHY"))
    degraded = compute_buy_score(assessment, _context(feed_status="DEGRADED"))
    assert healthy.feed_health == POINTS_FEED_HEALTH
    assert degraded.feed_health == 0


def test_market_state_category_points() -> None:
    assessment = _assessment(DecisionAssessmentState.BLOCKED)
    active = compute_buy_score(assessment, _context(state="ACTIVE", behavior="UNSTABLE"))
    trending = compute_buy_score(
        assessment, _context(state="TRENDING", behavior="UNSTABLE")
    )
    volatile = compute_buy_score(
        assessment, _context(state="VOLATILE", behavior="UNSTABLE")
    )
    assert active.market_state == POINTS_MARKET_STATE
    assert trending.market_state == POINTS_MARKET_STATE
    assert volatile.market_state == 0


def test_behavior_category_points() -> None:
    assessment = _assessment(DecisionAssessmentState.BLOCKED)
    stable = compute_buy_score(
        assessment, _context(state="QUIET", behavior="STABLE")
    )
    accelerating = compute_buy_score(
        assessment, _context(state="QUIET", behavior="ACCELERATING")
    )
    unstable = compute_buy_score(
        assessment, _context(state="QUIET", behavior="UNSTABLE")
    )
    assert stable.behavior == POINTS_BEHAVIOR
    assert accelerating.behavior == POINTS_BEHAVIOR
    assert unstable.behavior == 0


def test_physics_category_points() -> None:
    assessment = _assessment(DecisionAssessmentState.BLOCKED)
    positive = compute_buy_score(assessment, None, _physics(velocity=1.0, acceleration=0.2))
    negative_v = compute_buy_score(
        assessment, None, _physics(velocity=-1.0, acceleration=0.2)
    )
    negative_a = compute_buy_score(
        assessment, None, _physics(velocity=1.0, acceleration=-0.2)
    )
    missing = compute_buy_score(assessment, None, None)
    assert positive.physics == POINTS_PHYSICS
    assert negative_v.physics == 0
    assert negative_a.physics == 0
    assert missing.physics == 0


def test_liquidity_category_points() -> None:
    assessment = _assessment(DecisionAssessmentState.BLOCKED)
    both_buy = compute_buy_score(assessment, None, None, _liquidity())
    shift_sell = compute_buy_score(
        assessment,
        None,
        None,
        _liquidity(liquidity_shift=LiquidityBias.SELL.value),
    )
    imbalance_sell = compute_buy_score(
        assessment,
        None,
        None,
        _liquidity(dom_imbalance=LiquidityBias.SELL.value),
    )
    missing = compute_buy_score(assessment, None, None, None)
    assert both_buy.liquidity == POINTS_LIQUIDITY
    assert shift_sell.liquidity == 0
    assert imbalance_sell.liquidity == 0
    assert missing.liquidity == 0


def test_partial_score_example_65() -> None:
    """Assessment(20) + Feed(15) + State(15) + Behavior(15) = 65."""
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context(state="ACTIVE", behavior="STABLE", feed_status="HEALTHY")
    breakdown = compute_buy_score(assessment, context, None, None)
    assert breakdown.total == 65
    snap = apply_trade_decision_policy(
        assessment, context, None, None, timestamp=2.0
    )
    assert snap.buy_score == 65
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.reason == format_buy_score_reason(65)


def test_buy_never_emitted_across_scores() -> None:
    cases = (
        (_assessment(DecisionAssessmentState.BLOCKED), None, None, None),
        (
            _assessment(DecisionAssessmentState.READY),
            _context(),
            _physics(),
            _liquidity(),
        ),
        (
            _assessment(DecisionAssessmentState.READY),
            _context(state="VOLATILE"),
            _physics(velocity=-1.0),
            _liquidity(liquidity_shift=LiquidityBias.SELL.value),
        ),
    )
    for assessment, context, physics, liquidity in cases:
        snap = apply_trade_decision_policy(
            assessment, context, physics, liquidity, timestamp=3.0
        )
        assert snap.decision is TradeDecision.NO_TRADE
        assert snap.decision is not TradeDecision.BUY
        assert "Awaiting release." in snap.reason


def test_sell_remains_unavailable() -> None:
    values = {item.value for item in TradeDecision}
    assert "BUY" in values
    assert "SELL" not in values


def test_engine_delegates_to_policy() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context()
    physics = _physics()
    liquidity = _liquidity()
    via_engine = evaluate_trade_decision(
        assessment, context, physics, liquidity, timestamp=4.0
    )
    via_policy = apply_trade_decision_policy(
        assessment, context, physics, liquidity, timestamp=4.0
    )
    assert via_engine == via_policy
    assert via_engine.buy_score == 100
    assert via_engine.decision is TradeDecision.NO_TRADE


def test_engine_evaluate_and_snapshot() -> None:
    clock = iter([10.0, 11.0]).__next__
    engine = TradeDecisionEngine(clock=clock)
    snap = engine.evaluate(
        _assessment(DecisionAssessmentState.READY),
        _context(),
        _physics(),
        _liquidity(),
    )
    assert snap.buy_score == 100
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.timestamp == 11.0
    assert engine.snapshot() is snap
