"""Unit tests for Decision Intent Engine (Sprint 12)."""

from __future__ import annotations

from hotirjam_ai5.decision_foundation import DecisionFoundationSnapshot
from hotirjam_ai5.decision_intent import (
    DecisionIntent,
    DecisionIntentEngine,
    evaluate_decision_intent,
)
from hotirjam_ai5.decision_intent.engine import (
    EVALUATE_NEXT,
    EVALUATE_REASON,
    OBSERVE_NEXT,
    OBSERVE_REASON,
    WAIT_NEXT,
    WAIT_REASON,
)


def _foundation(**overrides: object) -> DecisionFoundationSnapshot:
    base = {
        "timestamp": 100.0,
        "ready": True,
        "blocking_reason": "",
        "required_data_complete": True,
        "context_valid": True,
        "observation_complete": True,
        "summary": "Observation layer complete.",
    }
    base.update(overrides)
    return DecisionFoundationSnapshot(**base)  # type: ignore[arg-type]


def test_wait_when_foundation_missing() -> None:
    snap = evaluate_decision_intent(None, timestamp=1.0)
    assert snap.intent is DecisionIntent.WAIT
    assert snap.reason == WAIT_REASON
    assert snap.next_step == WAIT_NEXT


def test_wait_when_foundation_not_ready() -> None:
    snap = evaluate_decision_intent(
        _foundation(
            ready=False,
            blocking_reason="Waiting for market context.",
            required_data_complete=False,
            context_valid=False,
            observation_complete=False,
            summary="Waiting for market context.",
        ),
        timestamp=2.0,
    )
    assert snap.intent is DecisionIntent.WAIT
    assert snap.reason == WAIT_REASON
    assert snap.next_step == WAIT_NEXT


def test_observe_when_ready_but_incomplete() -> None:
    snap = evaluate_decision_intent(
        _foundation(
            ready=True,
            observation_complete=False,
            required_data_complete=True,
            context_valid=True,
        ),
        timestamp=3.0,
    )
    assert snap.intent is DecisionIntent.OBSERVE
    assert snap.reason == OBSERVE_REASON
    assert snap.next_step == OBSERVE_NEXT


def test_evaluate_when_observation_complete() -> None:
    snap = evaluate_decision_intent(_foundation(), timestamp=4.0)
    assert snap.intent is DecisionIntent.EVALUATE
    assert snap.reason == EVALUATE_REASON
    assert snap.next_step == EVALUATE_NEXT
    assert snap.timestamp == 4.0


def test_reason_and_next_step_generation() -> None:
    wait = evaluate_decision_intent(None, timestamp=5.0)
    observe = evaluate_decision_intent(
        _foundation(observation_complete=False),
        timestamp=6.0,
    )
    evaluate = evaluate_decision_intent(_foundation(), timestamp=7.0)

    assert wait.reason == "Observation layer is not ready."
    assert wait.next_step == "No further processing."
    assert observe.reason == "Observation stable."
    assert observe.next_step == "Continue monitoring."
    assert evaluate.reason == "Observation layer complete."
    assert evaluate.next_step == "Begin evaluation when available."


def test_engine_evaluate_and_snapshot() -> None:
    clock = iter([10.0, 11.0]).__next__
    engine = DecisionIntentEngine(clock=clock)
    snap = engine.evaluate(_foundation())
    assert snap.intent is DecisionIntent.EVALUATE
    assert snap.timestamp == 11.0
    assert engine.snapshot() is snap


def test_output_never_contains_trading_words() -> None:
    cases = [
        None,
        _foundation(ready=False, observation_complete=False, context_valid=False),
        _foundation(observation_complete=False),
        _foundation(),
    ]
    banned = (
        "buy",
        "sell",
        "long",
        "short",
        "entry",
        "exit",
        "signal",
        "confidence",
        "probability",
        "risk",
    )
    for foundation in cases:
        snap = evaluate_decision_intent(foundation, timestamp=1.0)
        text = f"{snap.intent.value} {snap.reason} {snap.next_step}".lower()
        for word in banned:
            assert word not in text
