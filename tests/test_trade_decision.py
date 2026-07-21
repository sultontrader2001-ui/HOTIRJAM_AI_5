"""Unit tests for Trade Decision Policy — BUY Score + Confidence (Sprint 25)."""

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
    build_decision_explanation,
    compute_buy_confidence,
    compute_buy_score,
    evaluate_trade_decision,
    is_buy_eligible,
)
from hotirjam_ai5.trade_decision.models import ExplanationStatus
from hotirjam_ai5.trade_decision.policy import (
    CONF_ASSESSMENT_RELIABILITY,
    CONF_FEED_RELIABILITY,
    CONF_LIQUIDITY_RELIABILITY,
    CONF_MARKET_STABILITY,
    CONF_PHYSICS_STABILITY,
    CONF_TOTAL,
    NEXT_ACTION,
    POINTS_ASSESSMENT,
    POINTS_BEHAVIOR,
    POINTS_FEED_HEALTH,
    POINTS_LIQUIDITY,
    POINTS_MARKET_STATE,
    POINTS_PHYSICS,
    POINTS_TOTAL,
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
    confidence: float = 0.5,
) -> LiquiditySnapshot:
    return LiquiditySnapshot(
        timestamp=100.0,
        liquidity_shift=liquidity_shift,
        dom_imbalance=dom_imbalance,
        confidence=confidence,
    )


def test_full_score_and_confidence_still_no_trade() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context()
    physics = _physics()
    liquidity = _liquidity()

    score = compute_buy_score(assessment, context, physics, liquidity)
    confidence = compute_buy_confidence(assessment, context, physics, liquidity)
    assert score.total == POINTS_TOTAL
    assert confidence.total == CONF_TOTAL
    assert is_buy_eligible(assessment, context, physics, liquidity) is True

    snap = apply_trade_decision_policy(
        assessment, context, physics, liquidity, timestamp=1.0
    )
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.decision is not TradeDecision.BUY
    assert snap.buy_score == 100
    assert snap.buy_confidence == 100
    assert snap.reason == "BUY requirements are satisfied. Awaiting release."
    assert snap.next_action == NEXT_ACTION


def test_score_and_confidence_are_independent() -> None:
    """Score can award state/behavior separately; confidence combines them."""
    assessment = _assessment(DecisionAssessmentState.READY)
    # State eligible, behavior not — score gets state points, confidence market=0.
    context = _context(state="ACTIVE", behavior="UNSTABLE", feed_status="HEALTHY")
    score = compute_buy_score(assessment, context, None, None)
    confidence = compute_buy_confidence(assessment, context, None, None)
    assert score.assessment == POINTS_ASSESSMENT
    assert score.feed_health == POINTS_FEED_HEALTH
    assert score.market_state == POINTS_MARKET_STATE
    assert score.behavior == 0
    assert score.total == POINTS_ASSESSMENT + POINTS_FEED_HEALTH + POINTS_MARKET_STATE
    assert confidence.assessment_reliability == CONF_ASSESSMENT_RELIABILITY
    assert confidence.feed_reliability == CONF_FEED_RELIABILITY
    assert confidence.market_stability == 0
    assert confidence.total == CONF_ASSESSMENT_RELIABILITY + CONF_FEED_RELIABILITY
    assert score.total != confidence.total


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


def test_confidence_category_points() -> None:
    assessment = _assessment(DecisionAssessmentState.READY)
    full = compute_buy_confidence(
        assessment, _context(), _physics(), _liquidity()
    )
    assert full.assessment_reliability == CONF_ASSESSMENT_RELIABILITY
    assert full.feed_reliability == CONF_FEED_RELIABILITY
    assert full.physics_stability == CONF_PHYSICS_STABILITY
    assert full.liquidity_reliability == CONF_LIQUIDITY_RELIABILITY
    assert full.market_stability == CONF_MARKET_STABILITY
    assert full.total == CONF_TOTAL


def test_confidence_boundaries() -> None:
    zero = compute_buy_confidence(
        _assessment(DecisionAssessmentState.BLOCKED), None, None, None
    )
    assert zero.total == 0
    assert 0 <= zero.total <= CONF_TOTAL

    full = compute_buy_confidence(
        _assessment(DecisionAssessmentState.READY),
        _context(),
        _physics(),
        _liquidity(),
    )
    assert full.total == CONF_TOTAL
    assert 0 <= full.total <= CONF_TOTAL

    partial = compute_buy_confidence(
        _assessment(DecisionAssessmentState.READY),
        _context(feed_status="DEGRADED", state="VOLATILE", behavior="UNSTABLE"),
        _physics(velocity=-1.0),
        _liquidity(liquidity_shift=LiquidityBias.SELL.value),
    )
    assert partial.total == CONF_ASSESSMENT_RELIABILITY
    assert 0 <= partial.total <= CONF_TOTAL


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
    assert snap.buy_confidence == (
        CONF_ASSESSMENT_RELIABILITY + CONF_FEED_RELIABILITY + CONF_MARKET_STABILITY
    )
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.decision_explanation is not None
    assert snap.decision_explanation.physics is ExplanationStatus.UNKNOWN
    assert snap.decision_explanation.liquidity is ExplanationStatus.UNKNOWN
    assert snap.reason == snap.decision_explanation.summary


def test_explanation_all_pass() -> None:
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _context(),
        _physics(),
        _liquidity(),
        timestamp=5.0,
    )
    expl = snap.decision_explanation
    assert expl is not None
    assert expl.assessment is ExplanationStatus.PASS
    assert expl.feed is ExplanationStatus.PASS
    assert expl.market_state is ExplanationStatus.PASS
    assert expl.behavior is ExplanationStatus.PASS
    assert expl.physics is ExplanationStatus.PASS
    assert expl.liquidity is ExplanationStatus.PASS
    assert expl.summary == "BUY requirements are satisfied. Awaiting release."
    assert snap.decision is TradeDecision.NO_TRADE


def test_explanation_pass_fail_unknown_combo() -> None:
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _context(state="VOLATILE", behavior="UNSTABLE", feed_status="HEALTHY"),
        None,
        None,
        timestamp=6.0,
    )
    expl = snap.decision_explanation
    assert expl is not None
    assert expl.assessment is ExplanationStatus.PASS
    assert expl.feed is ExplanationStatus.PASS
    assert expl.market_state is ExplanationStatus.FAIL
    assert expl.behavior is ExplanationStatus.FAIL
    assert expl.physics is ExplanationStatus.UNKNOWN
    assert expl.liquidity is ExplanationStatus.UNKNOWN
    assert expl.summary == "Market is volatile and physics confirmation is missing."


def test_explanation_unknown_when_inputs_missing() -> None:
    expl = build_decision_explanation(
        _assessment(DecisionAssessmentState.BLOCKED), None, None, None
    )
    assert expl.assessment is ExplanationStatus.FAIL
    assert expl.feed is ExplanationStatus.UNKNOWN
    assert expl.market_state is ExplanationStatus.UNKNOWN
    assert expl.behavior is ExplanationStatus.UNKNOWN
    assert expl.physics is ExplanationStatus.UNKNOWN
    assert expl.liquidity is ExplanationStatus.UNKNOWN
    assert expl.summary == "Assessment is not READY for trade decision."


def test_explanation_default_fail_summary() -> None:
    expl = build_decision_explanation(
        _assessment(DecisionAssessmentState.READY),
        _context(state="QUIET", behavior="UNSTABLE", feed_status="DEGRADED"),
        _physics(velocity=-1.0),
        _liquidity(liquidity_shift=LiquidityBias.SELL.value),
    )
    assert expl.assessment is ExplanationStatus.PASS
    assert expl.feed is ExplanationStatus.FAIL
    assert expl.market_state is ExplanationStatus.FAIL
    assert expl.behavior is ExplanationStatus.FAIL
    assert expl.physics is ExplanationStatus.FAIL
    assert expl.liquidity is ExplanationStatus.FAIL
    assert expl.summary == "Market conditions do not satisfy BUY requirements."


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
        assert 0 <= snap.buy_score <= 100
        assert 0 <= snap.buy_confidence <= 100
        assert snap.decision_explanation is not None
        assert snap.reason == snap.decision_explanation.summary


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
    assert via_engine.buy_confidence == 100
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
    assert snap.buy_confidence == 100
    assert snap.decision is TradeDecision.NO_TRADE
    assert snap.timestamp == 11.0
    assert engine.snapshot() is snap
