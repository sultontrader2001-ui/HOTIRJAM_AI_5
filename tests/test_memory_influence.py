"""Tests for Market Memory Decision Integration (Sprint 44)."""

from __future__ import annotations

import pytest

from hotirjam_ai5.decision_assessment import (
    DecisionAssessmentSnapshot,
    DecisionAssessmentState,
)
from hotirjam_ai5.liquidity import LiquidityBias, LiquiditySnapshot
from hotirjam_ai5.market_context import MarketContextSnapshot
from hotirjam_ai5.memory.diagnostics_models import (
    BandSummary,
    ConsensusStatus,
    ConsensusSummary,
    MemoryBandName,
    MemoryDiagnosticsReport,
    SourceSummary,
    StoreDiagnosticsSummary,
)
from hotirjam_ai5.memory.memory_types import MemorySource
from hotirjam_ai5.physics.measurements import PhysicsSnapshot
from hotirjam_ai5.trade_decision import (
    MEMORY_MAX_BOOST,
    MEMORY_MAX_OPPOSE,
    apply_memory_score_influence,
    apply_trade_decision_policy,
    compute_buy_score,
    compute_memory_deltas,
)
from hotirjam_ai5.trade_decision.models import TradeDecision


def _assessment() -> DecisionAssessmentSnapshot:
    return DecisionAssessmentSnapshot(
        timestamp=1.0,
        assessment_state=DecisionAssessmentState.READY,
        assessment_ready=True,
        reason="fixture",
        next_stage="fixture",
    )


def _context(*, side: str = "BUY") -> MarketContextSnapshot:
    up = side == "BUY"
    return MarketContextSnapshot(
        timestamp=1.0,
        state="ACTIVE",
        state_reason="fixture",
        transition="NONE",
        transition_changed=False,
        transition_duration=1.0,
        behavior="STABLE",
        behavior_reason="fixture",
        feed_status="HEALTHY",
        feed_quality="GOOD",
        dom_status="HEALTHY",
        dom_quality="GOOD",
        tick_rate=8.0,
        spread=0.25,
        summary="fixture",
        state_direction="UP" if up else "DOWN",
        behavior_direction="BUY" if up else "SELL",
    )


def _physics(*, side: str = "BUY") -> PhysicsSnapshot:
    sign = 1.0 if side == "BUY" else -1.0
    return PhysicsSnapshot(
        spread=0.25,
        mid_price=20100.0,
        tick_velocity=sign * 2.0,
        tick_acceleration=sign * 0.5,
        tick_count=10,
    )


def _liquidity(*, side: str = "BUY") -> LiquiditySnapshot:
    bias = LiquidityBias.BUY.value if side == "BUY" else LiquidityBias.SELL.value
    return LiquiditySnapshot(
        timestamp=1.0,
        liquidity_shift=bias,
        dom_imbalance=bias,
        confidence=0.8,
    )


def _band(direction: str, *, persistence: float = 90.0) -> BandSummary:
    buy = 10 if direction == "BUY" else 0
    sell = 10 if direction == "SELL" else 0
    return BandSummary(
        name=MemoryBandName.FAST,
        window_seconds=10.0,
        direction=direction,
        buy_count=buy,
        sell_count=sell,
        neutral_count=0,
        strength=80.0,
        confidence=90.0,
        persistence=persistence,
        record_count=10,
    )


def _report(
    *,
    direction: str,
    status: ConsensusStatus,
    agreement: float,
    persistence: float = 90.0,
    confidence: float = 90.0,
) -> MemoryDiagnosticsReport:
    bands = (
        _band(direction, persistence=persistence),
        BandSummary(
            name=MemoryBandName.MEDIUM,
            window_seconds=30.0,
            direction=direction,
            buy_count=20,
            sell_count=0 if direction == "BUY" else 20,
            neutral_count=0,
            strength=75.0,
            confidence=confidence,
            persistence=persistence,
            record_count=20,
        ),
        BandSummary(
            name=MemoryBandName.SLOW,
            window_seconds=60.0,
            direction=direction,
            buy_count=30,
            sell_count=0 if direction == "BUY" else 30,
            neutral_count=0,
            strength=70.0,
            confidence=confidence,
            persistence=persistence,
            record_count=30,
        ),
    )
    if status is ConsensusStatus.MIXED:
        bands = (
            _band("SELL", persistence=persistence),
            bands[1],
            bands[2],
        )
    return MemoryDiagnosticsReport(
        bands=bands,
        sources=tuple(
            SourceSummary(
                source=src,
                current_direction=direction,
                average_strength=70.0,
                average_confidence=80.0,
                record_count=5,
                last_update=1.0,
            )
            for src in MemorySource
        ),
        consensus=ConsensusSummary(
            direction=direction if status is not ConsensusStatus.MIXED else "BUY",
            confidence=confidence,
            agreement=agreement,
            status=status,
            fast_direction=bands[0].direction,
            medium_direction=bands[1].direction,
            slow_direction=bands[2].direction,
        ),
        timeline=(),
        store=StoreDiagnosticsSummary(
            memory_size=10,
            capacity=2048,
            ring_buffer_usage=1.0,
            oldest_record=0.0,
            newest_record=1.0,
            records_per_source={src: 2 for src in MemorySource},
            average_append_rate=1.0,
        ),
        as_of=1.0,
    )


def test_buy_reinforcement_increases_buy_reduces_sell() -> None:
    report = _report(
        direction="BUY",
        status=ConsensusStatus.ALIGNED,
        agreement=96.0,
    )
    influence = apply_memory_score_influence(
        original_buy_score=80,
        original_sell_score=40,
        report=report,
    )
    assert influence.applied is True
    assert influence.buy_delta > 0
    assert influence.sell_delta < 0
    assert influence.adjusted_buy_score == 80 + influence.buy_delta
    assert influence.adjusted_sell_score == 40 + influence.sell_delta
    assert influence.buy_delta <= MEMORY_MAX_BOOST
    assert abs(influence.sell_delta) <= MEMORY_MAX_OPPOSE


def test_sell_reinforcement_increases_sell_reduces_buy() -> None:
    report = _report(
        direction="SELL",
        status=ConsensusStatus.ALIGNED,
        agreement=96.0,
    )
    influence = apply_memory_score_influence(
        original_buy_score=40,
        original_sell_score=80,
        report=report,
    )
    assert influence.applied is True
    assert influence.sell_delta > 0
    assert influence.buy_delta < 0


def test_mixed_consensus_no_adjustment() -> None:
    report = _report(
        direction="BUY",
        status=ConsensusStatus.MIXED,
        agreement=41.0,
    )
    buy_d, sell_d, applied = compute_memory_deltas(report)
    assert applied is False
    assert buy_d == 0 and sell_d == 0


def test_uncertain_and_neutral_no_adjustment() -> None:
    uncertain = _report(
        direction="BUY",
        status=ConsensusStatus.UNCERTAIN,
        agreement=40.0,
    )
    assert compute_memory_deltas(uncertain) == (0, 0, False)
    neutral = _report(
        direction="NEUTRAL",
        status=ConsensusStatus.ALIGNED,
        agreement=90.0,
    )
    assert compute_memory_deltas(neutral) == (0, 0, False)


def test_score_adjustment_limits_and_clamp() -> None:
    report = _report(
        direction="BUY",
        status=ConsensusStatus.ALIGNED,
        agreement=100.0,
        persistence=100.0,
        confidence=100.0,
    )
    influence = apply_memory_score_influence(
        original_buy_score=98,
        original_sell_score=1,
        report=report,
    )
    assert influence.buy_delta <= MEMORY_MAX_BOOST
    assert influence.adjusted_buy_score <= 100
    assert influence.adjusted_sell_score >= 0
    assert abs(influence.sell_delta) <= MEMORY_MAX_OPPOSE


def test_no_memory_available() -> None:
    influence = apply_memory_score_influence(
        original_buy_score=65,
        original_sell_score=35,
        report=None,
    )
    assert influence.applied is False
    assert influence.buy_delta == 0
    assert influence.sell_delta == 0
    assert influence.adjusted_buy_score == 65
    assert influence.adjusted_sell_score == 35


def test_policy_logs_memory_influence_and_uses_adjusted_scores() -> None:
    report = _report(
        direction="BUY",
        status=ConsensusStatus.ALIGNED,
        agreement=96.0,
    )
    snap = apply_trade_decision_policy(
        _assessment(),
        _context(),
        _physics(),
        _liquidity(),
        timestamp=1.0,
        memory_diagnostics=report,
    )
    mi = snap.memory_influence
    assert mi is not None
    assert mi.original_buy_score == 100
    assert mi.applied is True
    assert snap.buy_score == mi.adjusted_buy_score
    assert snap.sell_score == mi.adjusted_sell_score
    assert mi.consensus == "BUY"
    assert mi.agreement == pytest.approx(96.0)
    # Primary breakdown unchanged (Memory does not rewrite category math).
    assert snap.buy_score_breakdown is not None
    assert snap.buy_score_breakdown.total == mi.original_buy_score


def test_regression_without_memory_matches_primary_total() -> None:
    assessment = _assessment()
    context = _context()
    physics = _physics()
    liquidity = _liquidity()
    primary = compute_buy_score(assessment, context, physics, liquidity).total
    snap = apply_trade_decision_policy(
        assessment,
        context,
        physics,
        liquidity,
        timestamp=2.0,
        memory_diagnostics=None,
    )
    assert snap.buy_score == primary
    assert snap.memory_influence is not None
    assert snap.memory_influence.applied is False
    assert snap.decision is TradeDecision.NO_TRADE  # no stability history
