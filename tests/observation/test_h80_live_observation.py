"""H-8.0 Live Observation & Certification tests."""

from __future__ import annotations

import ast
from pathlib import Path

from hotirjam_ai5.break_capability import BreakCapabilitySnapshot
from hotirjam_ai5.continuation import ContinuationSnapshot
from hotirjam_ai5.dashboard.models import DashboardState, MarketStateView, TradeDecisionView
from hotirjam_ai5.initiative import InitiativeSnapshot
from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.live_validator.models import ValidatorFrame
from hotirjam_ai5.objective import ObjectiveSnapshot
from hotirjam_ai5.observation.app import main as observe_main
from hotirjam_ai5.observation.models import ObservationCycle
from hotirjam_ai5.observation.recorder import record_from_frame
from hotirjam_ai5.observation.report import build_certification_report
from hotirjam_ai5.observation.session import ObservationSession
from hotirjam_ai5.response import ResponseSnapshot

_OBS_ROOT = Path(__file__).resolve().parents[2] / "src" / "hotirjam_ai5" / "observation"


def _frame(*, ts: float = 10.0, price: float = 100.0) -> ValidatorFrame:
    return ValidatorFrame(
        timestamp=ts,
        current_price=price,
        symbol="MNQ",
        candle_count=3,
        swing_high_count=1,
        swing_low_count=1,
        objective=ObjectiveSnapshot(
            nearest_high_price=110.0,
            nearest_high_distance_ticks=40.0,
            nearest_high_strength=80.0,
            nearest_low_price=90.0,
            nearest_low_distance_ticks=40.0,
            nearest_low_strength=80.0,
            current_price=price,
            timestamp=ts,
        ),
        initiative=InitiativeSnapshot.empty(timestamp=ts),
        response=ResponseSnapshot.empty(timestamp=ts),
        continuation=ContinuationSnapshot.empty(timestamp=ts),
        break_capability=BreakCapabilitySnapshot.empty(timestamp=ts),
        decision="DISABLED",
    )


def _tick(i: int) -> LiveTick:
    px = 18000.0 + i * 0.25
    return LiveTick(
        timestamp=1_700_000_000.0 + i,
        symbol="MNQ",
        last_price=px,
        bid=px - 0.25,
        ask=px + 0.25,
        volume=1.0,
    )


def test_record_cycle_has_required_fields() -> None:
    cycle = record_from_frame(_frame(), cycle_id=1)
    assert cycle.time == 10.0
    assert "H=" in cycle.objective
    assert cycle.initiative
    assert cycle.response
    assert cycle.continuation
    assert cycle.break_capability
    assert cycle.confidence
    assert cycle.evidence
    assert cycle.no_trade_reason
    assert cycle.decision == "DISABLED"


def test_record_with_dashboard_market_and_reason() -> None:
    dash = DashboardState(
        market_state=MarketStateView(state="ACTIVE"),
        trade_decision=TradeDecisionView(
            decision="NO_TRADE",
            reason="Observation only",
        ),
    )
    cycle = record_from_frame(_frame(), cycle_id=1, dashboard=dash)
    assert cycle.market_state == "ACTIVE"
    assert cycle.decision == "NO_TRADE"
    assert cycle.no_trade_reason == "Observation only"


def test_session_records_and_passes() -> None:
    session = ObservationSession(min_cycles=2, clock=lambda: 100.0)
    session.record_frame(_frame(ts=1.0))
    session.record_frame(_frame(ts=2.0, price=101.0))
    report = session.finish()
    assert report.verdict == "PASS"
    assert report.cycle_count == 2
    assert "PASS" in report.as_text()


def test_certification_fails_on_zero_cycles() -> None:
    report = build_certification_report([], duration_seconds=1.0, min_cycles=1)
    assert report.verdict == "FAIL"


def test_certification_fails_on_forbidden_decision() -> None:
    evil = ObservationCycle(
        cycle_id=1,
        time=1.0,
        objective="x",
        initiative="x",
        response="x",
        continuation="x",
        break_capability="x",
        confidence="0",
        market_state="x",
        evidence="x",
        no_trade_reason="x",
        decision="BUY",
    )
    report = build_certification_report([evil], duration_seconds=0.1, min_cycles=1)
    assert report.verdict == "FAIL"
    assert any("forbidden" in r.lower() for r in report.reasons)


def test_observe_live_demo_ticks() -> None:
    ticks = [_tick(i) for i in range(40)]
    session = ObservationSession(min_cycles=5)
    report = session.observe_live(ticks, max_cycles=5)
    assert report.verdict == "PASS"
    assert report.cycle_count == 5
    assert all(c.decision == "DISABLED" for c in report.cycles)


def test_cli_demo_pass() -> None:
    code = observe_main(["--mode", "demo", "--max-cycles", "3", "--min-cycles", "3"])
    assert code == 0


def test_observation_layer_has_no_broker_or_hub_publish() -> None:
    forbidden_substrings = (
        "publish_dashboard",
        "publish_frame",
        "submit_order",
        "place_order",
    )
    for path in sorted(_OBS_ROOT.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for needle in forbidden_substrings:
            assert needle not in text, f"{path.name} contains {needle}"
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "broker" not in node.module.lower()
