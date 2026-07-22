"""H-8.1 Replay Validator certification tests."""

from __future__ import annotations

import ast
import copy
from dataclasses import asdict
from pathlib import Path

from hotirjam_ai5.observation.models import ObservationCycle
from hotirjam_ai5.replay.engine import ReplayValidator
from hotirjam_ai5.replay.models import ConfidenceLabel, MarketPoint, ModuleVerdict
from hotirjam_ai5.replay.report import format_replay_report

_REPLAY_ROOT = Path(__file__).resolve().parents[2] / "src" / "hotirjam_ai5" / "replay"


def _cycle(
    *,
    cycle_id: int = 1,
    time: float = 100.0,
    objective: str = "H=101.0 L=99.0",
    initiative: str = "BUYER ACTIVE c=0.80",
    response: str = "NONE NEUTRAL s=0.00",
    continuation: str = "BUYER WEAK sc=0.10",
    break_capability: str = "NONE WEAK p=0.10",
    confidence: str = "0.50",
    price: str = "100.0",
) -> ObservationCycle:
    return ObservationCycle(
        cycle_id=cycle_id,
        time=time,
        objective=objective,
        initiative=initiative,
        response=response,
        continuation=continuation,
        break_capability=break_capability,
        confidence=confidence,
        market_state="ACTIVE",
        evidence="force=1 energy=1 liq=1",
        no_trade_reason="decision=DISABLED",
        decision="DISABLED",
        symbol="MNQ",
        price=price,
    )


def test_replay_never_mutates_observations() -> None:
    obs = (_cycle(),)
    before = copy.deepcopy(asdict(obs[0]))
    market = (
        MarketPoint(time=100.0, price=100.0),
        MarketPoint(time=101.0, price=100.25),
        MarketPoint(time=102.0, price=100.50),
    )
    ReplayValidator().replay(obs, market)
    assert asdict(obs[0]) == before


def test_replay_deterministic_identical_fingerprint() -> None:
    obs = (_cycle(), _cycle(cycle_id=2, time=105.0, price="100.5"))
    market = tuple(
        MarketPoint(time=100.0 + i, price=100.0 + (i % 3) * 0.25) for i in range(20)
    )
    a = ReplayValidator().replay(obs, market)
    b = ReplayValidator().replay(obs, market)
    assert a.deterministic_fingerprint == b.deterministic_fingerprint
    assert a.results == b.results
    assert a.verdict == b.verdict


def test_objective_fail_when_band_broken() -> None:
    obs = (_cycle(objective="H=100.5 L=99.5", price="100.0"),)
    market = (
        MarketPoint(time=100.0, price=100.0),
        MarketPoint(time=101.0, price=101.5),  # breaks high
    )
    report = ReplayValidator().replay(obs, market)
    assert report.results[0].objective is ModuleVerdict.FAIL


def test_initiative_buyer_pass_on_up_drift() -> None:
    obs = (_cycle(initiative="BUYER ACTIVE c=0.70", price="100.0"),)
    market = (
        MarketPoint(time=100.0, price=100.0),
        MarketPoint(time=101.0, price=100.50),
        MarketPoint(time=102.0, price=100.75),
    )
    report = ReplayValidator().replay(obs, market)
    assert report.results[0].initiative is ModuleVerdict.PASS


def test_confidence_too_high() -> None:
    # High confidence but force fails via broken band + reverse move
    obs = (
        _cycle(
            objective="H=100.25 L=99.75",
            initiative="BUYER ACTIVE c=0.90",
            confidence="0.90",
            continuation="BUYER STRONG sc=0.90",
            break_capability="HIGH SUFFICIENT p=0.90",
            price="100.0",
        ),
    )
    market = (
        MarketPoint(time=100.0, price=100.0),
        MarketPoint(time=101.0, price=99.0),  # reverse + break low
    )
    report = ReplayValidator().replay(obs, market)
    assert report.results[0].confidence is ConfidenceLabel.TOO_HIGH


def test_report_contains_sections() -> None:
    obs = (_cycle(),)
    market = (
        MarketPoint(time=100.0, price=100.0),
        MarketPoint(time=101.0, price=100.0),
    )
    text = format_replay_report(ReplayValidator().replay(obs, market))
    assert "Session Verdict:" in text
    assert "Session Summary:" in text
    assert "Per Observation" in text
    assert "Objective" in text
    assert "Confidence" in text


def test_session_pass_on_consistent_path() -> None:
    obs = (
        _cycle(
            initiative="NONE NONE c=0.00",
            confidence="0.40",
            continuation="NONE WEAK sc=0.00",
            break_capability="NONE WEAK p=0.10",
        ),
    )
    market = (
        MarketPoint(time=100.0, price=100.0),
        MarketPoint(time=101.0, price=100.0),
        MarketPoint(time=102.0, price=100.25),
    )
    report = ReplayValidator().replay(obs, market)
    assert report.verdict == "PASS"


def test_replay_layer_has_no_hub_publish_or_orders() -> None:
    forbidden = ("publish_dashboard", "publish_frame", "submit_order", "place_order")
    for path in sorted(_REPLAY_ROOT.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for needle in forbidden:
            assert needle not in text, f"{path.name} contains {needle}"
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "broker" not in node.module.lower()
                assert not node.module.startswith("hotirjam_ai5.trade_decision")
                assert not node.module.startswith("hotirjam_ai5.decision_")
