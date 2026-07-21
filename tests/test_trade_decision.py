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
    compute_sell_confidence,
    compute_sell_score,
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
    state_direction: str = "UP",
    behavior_direction: str = "BUY",
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
        state_direction=state_direction,
        behavior_direction=behavior_direction,
    )


def _sell_context(
    *,
    state: str = "ACTIVE",
    behavior: str = "STABLE",
    feed_status: str = "HEALTHY",
) -> MarketContextSnapshot:
    return _context(
        state=state,
        behavior=behavior,
        feed_status=feed_status,
        state_direction="DOWN",
        behavior_direction="SELL",
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
    assert snap.decision is not TradeDecision.BUY_INTERNAL
    assert snap.buy_score == 100
    assert snap.buy_confidence == 100
    assert snap.signal_stability.value == "UNSTABLE"  # window not yet full
    assert snap.decision_explanation is not None
    assert snap.decision_explanation.signal_stability is ExplanationStatus.UNKNOWN
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
    history = ((100, 100), (100, 100))
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _context(),
        _physics(),
        _liquidity(),
        timestamp=5.0,
        signal_history=history,
    )
    expl = snap.decision_explanation
    assert expl is not None
    assert expl.assessment is ExplanationStatus.PASS
    assert expl.feed is ExplanationStatus.PASS
    assert expl.market_state is ExplanationStatus.PASS
    assert expl.behavior is ExplanationStatus.PASS
    assert expl.physics is ExplanationStatus.PASS
    assert expl.liquidity is ExplanationStatus.PASS
    assert expl.signal_stability is ExplanationStatus.PASS
    assert expl.readiness is ExplanationStatus.PASS
    assert snap.signal_stability.value == "STABLE"
    assert snap.decision_readiness.value == "READY"
    assert expl.summary == (
        "BUY requirements are satisfied and Decision Readiness is READY. "
        "Awaiting release."
    )
    assert snap.decision is TradeDecision.BUY_INTERNAL


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
    assert expl.readiness is ExplanationStatus.UNKNOWN
    assert snap.decision_readiness.value == "UNKNOWN"
    assert expl.summary == "Decision Readiness is UNKNOWN."


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
    assert expl.readiness is ExplanationStatus.UNKNOWN
    assert expl.summary == "Decision Readiness is UNKNOWN."


def test_explanation_default_fail_summary() -> None:
    history = ((90, 90), (91, 91))
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _context(state="QUIET", behavior="UNSTABLE", feed_status="DEGRADED"),
        _physics(velocity=-1.0),
        _liquidity(liquidity_shift=LiquidityBias.SELL.value),
        timestamp=7.0,
        signal_history=history,
    )
    expl = snap.decision_explanation
    assert expl is not None
    assert expl.assessment is ExplanationStatus.PASS
    assert expl.feed is ExplanationStatus.FAIL
    assert expl.market_state is ExplanationStatus.FAIL
    assert expl.behavior is ExplanationStatus.FAIL
    assert expl.physics is ExplanationStatus.FAIL
    assert expl.liquidity is ExplanationStatus.FAIL
    assert snap.decision_readiness.value == "NOT_READY"
    assert expl.readiness is ExplanationStatus.FAIL
    assert "Decision Readiness is NOT_READY." in expl.summary


def test_decision_readiness_ready_path() -> None:
    history = ((88, 92), (90, 90))
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _context(),
        _physics(),
        _liquidity(),
        timestamp=30.0,
        signal_history=history,
    )
    assert snap.buy_score >= 80
    assert snap.buy_confidence >= 85
    assert snap.signal_stability.value == "STABLE"
    assert snap.decision_readiness.value == "READY"
    assert snap.decision_explanation is not None
    assert snap.decision_explanation.readiness is ExplanationStatus.PASS
    assert snap.decision is TradeDecision.BUY_INTERNAL


def test_decision_readiness_not_ready_path() -> None:
    history = ((90, 90), (91, 91))
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _context(feed_status="DEGRADED"),
        _physics(),
        _liquidity(),
        timestamp=31.0,
        signal_history=history,
    )
    # Degraded feed lowers confidence below readiness threshold.
    assert snap.decision_readiness.value == "NOT_READY"
    assert snap.decision_explanation is not None
    assert snap.decision_explanation.readiness is ExplanationStatus.FAIL
    assert snap.decision is TradeDecision.NO_TRADE


def test_decision_readiness_unknown_path() -> None:
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _context(),
        _physics(),
        None,
        timestamp=32.0,
        signal_history=((95, 95), (96, 96)),
    )
    assert snap.decision_readiness.value == "UNKNOWN"
    assert snap.decision_explanation is not None
    assert snap.decision_explanation.readiness is ExplanationStatus.UNKNOWN
    assert snap.decision_explanation.summary == "Decision Readiness is UNKNOWN."


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
        assert snap.decision is not TradeDecision.BUY_INTERNAL
        assert 0 <= snap.buy_score <= 100
        assert 0 <= snap.buy_confidence <= 100
        assert snap.decision_explanation is not None
        assert snap.reason == snap.decision_explanation.summary


def test_sell_remains_unavailable_as_tradable() -> None:
    values = {item.value for item in TradeDecision}
    assert "BUY_INTERNAL" in values
    assert "SELL_INTERNAL" in values
    assert "BUY" not in values
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
    clock = iter([10.0, 11.0, 12.0, 13.0]).__next__
    engine = TradeDecisionEngine(clock=clock)
    for _ in range(2):
        snap = engine.evaluate(
            _assessment(DecisionAssessmentState.READY),
            _context(),
            _physics(),
            _liquidity(),
        )
        assert snap.signal_stability.value == "UNSTABLE"
        assert snap.decision is TradeDecision.NO_TRADE
    snap = engine.evaluate(
        _assessment(DecisionAssessmentState.READY),
        _context(),
        _physics(),
        _liquidity(),
    )
    assert snap.buy_score == 100
    assert snap.buy_confidence == 100
    assert snap.signal_stability.value == "STABLE"
    assert snap.decision_readiness.value == "READY"
    assert snap.decision is TradeDecision.BUY_INTERNAL
    assert engine.snapshot() is snap


def test_three_consecutive_qualifying_evaluations_stable() -> None:
    history = ((86, 92), (90, 88))
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _context(),
        _physics(),
        _liquidity(),
        timestamp=20.0,
        signal_history=history,
    )
    # Current eval is 100/100 — with prior two qualifying → STABLE
    assert snap.buy_score == 100
    assert snap.buy_confidence == 100
    assert snap.signal_stability.value == "STABLE"
    assert snap.decision_explanation is not None
    assert snap.decision_explanation.signal_stability is ExplanationStatus.PASS
    assert snap.decision_readiness.value == "READY"
    assert snap.decision is TradeDecision.BUY_INTERNAL


def test_interrupted_sequence_unstable() -> None:
    history = ((90, 90), (50, 90))  # second sample fails score threshold
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _context(),
        _physics(),
        _liquidity(),
        timestamp=21.0,
        signal_history=history,
    )
    assert snap.signal_stability.value == "UNSTABLE"
    assert snap.decision_explanation is not None
    assert snap.decision_explanation.signal_stability is ExplanationStatus.FAIL


def test_rolling_window_drops_old_samples() -> None:
    # Only last 3 matter; old failing sample outside window is ignored.
    history = ((10, 10), (90, 90), (91, 91))
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _context(),
        _physics(),
        _liquidity(),
        timestamp=22.0,
        signal_history=history,
    )
    # Window becomes (90,90), (91,91), (100,100) — STABLE
    assert snap.signal_stability.value == "STABLE"


def test_signal_stability_unknown_until_window_full() -> None:
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _context(),
        _physics(),
        _liquidity(),
        timestamp=23.0,
        signal_history=((95, 95),),
    )
    assert snap.signal_stability.value == "UNSTABLE"
    assert snap.decision_explanation is not None
    assert snap.decision_explanation.signal_stability is ExplanationStatus.UNKNOWN


def test_sell_ready_returns_sell_internal() -> None:
    history = ((88, 92), (90, 90))
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _sell_context(),
        _physics(velocity=-1.5, acceleration=-0.3),
        _liquidity(
            liquidity_shift=LiquidityBias.SELL.value,
            dom_imbalance=LiquidityBias.SELL.value,
        ),
        timestamp=40.0,
        sell_signal_history=history,
    )
    assert snap.sell_score == 100
    assert snap.sell_confidence == 100
    assert snap.sell_signal_stability.value == "STABLE"
    assert snap.sell_decision_readiness.value == "READY"
    assert snap.decision_readiness.value != "READY"
    assert snap.decision is TradeDecision.SELL_INTERNAL
    assert snap.decision is not TradeDecision.BUY_INTERNAL


def test_sell_not_ready_returns_no_trade() -> None:
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _sell_context(),
        _physics(velocity=-1.0, acceleration=-0.2),
        _liquidity(
            liquidity_shift=LiquidityBias.SELL.value,
            dom_imbalance=LiquidityBias.SELL.value,
        ),
        timestamp=41.0,
    )
    assert snap.sell_score == 100
    assert snap.sell_decision_readiness.value == "UNKNOWN"
    assert snap.decision is TradeDecision.NO_TRADE


def test_sell_priority_over_buy_when_both_would_compete() -> None:
    """Guard: if both ready, SELL wins and BUY is demoted."""
    from hotirjam_ai5.trade_decision.policy import resolve_trade_decision
    from hotirjam_ai5.trade_decision.models import DecisionReadiness

    assert (
        resolve_trade_decision(
            DecisionReadiness.READY,
            DecisionReadiness.READY,
        )
        is TradeDecision.SELL_INTERNAL
    )


def test_buy_vs_sell_priority_prefers_ready_sell() -> None:
    history = ((90, 90), (91, 91))
    snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _sell_context(),
        _physics(velocity=-2.0, acceleration=-0.4),
        _liquidity(
            liquidity_shift=LiquidityBias.SELL.value,
            dom_imbalance=LiquidityBias.SELL.value,
        ),
        timestamp=42.0,
        signal_history=history,  # BUY history would be weak with SELL physics
        sell_signal_history=history,
    )
    assert snap.decision is TradeDecision.SELL_INTERNAL
    assert snap.sell_decision_readiness.value == "READY"
    # BUY cannot be READY with negative physics / SELL liquidity.
    assert snap.decision_readiness.value != "READY"


def test_buy_and_sell_cannot_both_be_ready() -> None:
    history = ((95, 95), (96, 96))
    buy_snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _context(),
        _physics(velocity=1.0, acceleration=0.2),
        _liquidity(),
        timestamp=43.0,
        signal_history=history,
    )
    sell_snap = apply_trade_decision_policy(
        _assessment(DecisionAssessmentState.READY),
        _sell_context(),
        _physics(velocity=-1.0, acceleration=-0.2),
        _liquidity(
            liquidity_shift=LiquidityBias.SELL.value,
            dom_imbalance=LiquidityBias.SELL.value,
        ),
        timestamp=44.0,
        sell_signal_history=history,
    )
    assert buy_snap.decision_readiness.value == "READY"
    assert buy_snap.sell_decision_readiness.value != "READY"
    assert sell_snap.sell_decision_readiness.value == "READY"
    assert sell_snap.decision_readiness.value != "READY"


# --- Sprint 35 — signed Market State & Behavior ---


def test_up_trend_awards_buy_only() -> None:
    assessment = _assessment(DecisionAssessmentState.BLOCKED)
    context = _context(
        state="TRENDING",
        behavior="UNSTABLE",
        state_direction="UP",
    )
    buy = compute_buy_score(assessment, context)
    sell = compute_sell_score(assessment, context)
    assert buy.market_state == POINTS_MARKET_STATE
    assert sell.market_state == 0


def test_down_trend_awards_sell_only() -> None:
    assessment = _assessment(DecisionAssessmentState.BLOCKED)
    context = _context(
        state="TRENDING",
        behavior="UNSTABLE",
        state_direction="DOWN",
    )
    buy = compute_buy_score(assessment, context)
    sell = compute_sell_score(assessment, context)
    assert buy.market_state == 0
    assert sell.market_state == POINTS_MARKET_STATE


def test_buy_accelerating_awards_buy_only() -> None:
    assessment = _assessment(DecisionAssessmentState.BLOCKED)
    context = _context(
        state="QUIET",
        behavior="ACCELERATING",
        behavior_direction="BUY",
    )
    buy = compute_buy_score(assessment, context)
    sell = compute_sell_score(assessment, context)
    assert buy.behavior == POINTS_BEHAVIOR
    assert sell.behavior == 0


def test_sell_accelerating_awards_sell_only() -> None:
    assessment = _assessment(DecisionAssessmentState.BLOCKED)
    context = _context(
        state="QUIET",
        behavior="ACCELERATING",
        behavior_direction="SELL",
    )
    buy = compute_buy_score(assessment, context)
    sell = compute_sell_score(assessment, context)
    assert buy.behavior == 0
    assert sell.behavior == POINTS_BEHAVIOR


def test_neutral_direction_awards_neither_side() -> None:
    assessment = _assessment(DecisionAssessmentState.BLOCKED)
    context = _context(
        state="TRENDING",
        behavior="STABLE",
        state_direction="NEUTRAL",
        behavior_direction="NEUTRAL",
    )
    buy = compute_buy_score(assessment, context)
    sell = compute_sell_score(assessment, context)
    assert buy.market_state == 0
    assert buy.behavior == 0
    assert sell.market_state == 0
    assert sell.behavior == 0


def test_directional_context_separates_buy_and_sell_scores() -> None:
    """Sprint 34 finding: shared regime no longer produces equal full scores."""
    assessment = _assessment(DecisionAssessmentState.READY)
    context = _context(state_direction="UP", behavior_direction="BUY")
    physics = _physics(velocity=1.0, acceleration=0.2)
    liquidity = _liquidity()
    buy = compute_buy_score(assessment, context, physics, liquidity)
    sell = compute_sell_score(assessment, context, physics, liquidity)
    assert buy.total == 100
    assert sell.total == 35  # assessment + feed only
    assert buy.total != sell.total


def test_confidence_market_stability_is_directional() -> None:
    assessment = _assessment(DecisionAssessmentState.BLOCKED)
    up = _context(state_direction="UP", behavior_direction="BUY")
    down = _context(state_direction="DOWN", behavior_direction="SELL")
    assert compute_buy_confidence(assessment, up).market_stability == (
        CONF_MARKET_STABILITY
    )
    assert compute_sell_confidence(assessment, up).market_stability == 0
    assert compute_buy_confidence(assessment, down).market_stability == 0
    assert compute_sell_confidence(assessment, down).market_stability == (
        CONF_MARKET_STABILITY
    )
