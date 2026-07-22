"""H-7.2 Mission Control live wiring — read-only provenance certification."""

from __future__ import annotations

import ast
import time
from pathlib import Path

from hotirjam_ai5.break_capability import BreakCapabilitySnapshot
from hotirjam_ai5.continuation import ContinuationSnapshot
from hotirjam_ai5.dashboard.models import (
    AccountStatusView,
    DashboardState,
    FeedHealthView,
    FeedStatus,
    LiveMarketView,
    SignalHistoryRowView,
    StatisticsView,
    SystemView,
    TradeDecisionView,
    EngineStatus,
    MarketStatus,
)
from hotirjam_ai5.initiative import InitiativeSnapshot
from hotirjam_ai5.live_validator.loop_timing import LoopTimingSnapshot, TimingSeverity
from hotirjam_ai5.live_validator.models import ValidatorFrame
from hotirjam_ai5.mission_control.bind_cockpit import bind_cockpit_fields
from hotirjam_ai5.mission_control.bind_laboratory import bind_laboratory_cards
from hotirjam_ai5.mission_control.catalog import default_module_cards
from hotirjam_ai5.mission_control.cockpit import render_cockpit
from hotirjam_ai5.mission_control.laboratory import render_laboratory
from hotirjam_ai5.mission_control.runtime_bundle import RuntimeBundle
from hotirjam_ai5.mission_control.shell import MissionControlShell
from hotirjam_ai5.objective import ObjectiveSnapshot
from hotirjam_ai5.response import ResponseSnapshot

_MC_ROOT = Path(__file__).resolve().parents[2] / "src" / "hotirjam_ai5" / "mission_control"

_FORBIDDEN_CALL_NAMES = frozenset(
    {"evaluate", "calculate", "recompute", "predict", "derive", "derive_diagnostic_log"}
)
_FORBIDDEN_IMPORT_PREFIXES = (
    "hotirjam_ai5.objective.objective_engine",
    "hotirjam_ai5.objective_diagnostics.objective_audit",
    "hotirjam_ai5.objective_diagnostics.persistent_hierarchy",
    "hotirjam_ai5.response.response_engine",
    "hotirjam_ai5.continuation.continuation_engine",
    "hotirjam_ai5.break_capability.break_engine",
    "hotirjam_ai5.initiative.initiative_engine",
    "hotirjam_ai5.physics.engine",
    "hotirjam_ai5.liquidity.engine",
    "hotirjam_ai5.market_state.engine",
    "hotirjam_ai5.trade_decision",
    "hotirjam_ai5.decision_",
)


def _empty_frame(*, ts: float = 10.0, price: float = 100.0) -> ValidatorFrame:
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


def test_empty_bundle_unwired() -> None:
    sections = bind_cockpit_fields(RuntimeBundle(now=time.time()))
    assert sections["market"]["Last Price"].value in {"N/A", "UNWIRED"}
    assert sections["next_trigger"]["Condition"].value == "UNWIRED"
    assert "No timeline available" in sections["ai_timeline"]["Available"].value


def test_dashboard_market_provenance() -> None:
    dash = DashboardState(
        market=LiveMarketView(
            symbol="MNQ", last_price=100.25, bid=100.0, ask=100.5
        ),
        statistics=StatisticsView(tick_rate=12.5),
        system=SystemView(
            engine_status=EngineStatus.RUNNING,
            market_status=MarketStatus.OPEN,
        ),
        feed_health=FeedHealthView(feed_status=FeedStatus.HEALTHY),
        trade_decision=TradeDecisionView(
            decision="BUY_INTERNAL",
            buy_confidence=70,
            reason="test reason",
            next_action="HOLD",
        ),
        account_status=AccountStatusView(current_equity=50_000.0, today_pnl=12.0),
        events=("Connected", "Feed resumed"),
        signal_history=(
            SignalHistoryRowView(
                index=1, time_label="12:00", direction="BUY", result="WIN", points=2.0
            ),
        ),
    )
    sections = bind_cockpit_fields(RuntimeBundle(now=time.time(), dashboard=dash))
    last = sections["market"]["Last Price"]
    assert last.value == "100.25"
    assert last.source_object == "DashboardState.market"
    assert last.source_field == "last_price"
    assert sections["ai_decision"]["Direction"].value == "BUY_INTERNAL"
    assert sections["ai_decision"]["Grade"].value == "N/A"
    assert sections["next_trigger"]["Condition"].value == "UNWIRED"
    assert sections["account"]["Equity"].value == "50000.00"
    assert sections["system_health"]["Feed"].value == "HEALTHY"
    assert "BUY" in sections["ai_timeline"]["Event[0]"].value
    assert len(sections["recent_events"]) == 2


def test_frame_objective_and_lab_bound() -> None:
    frame = _empty_frame()
    bundle = RuntimeBundle(now=frame.timestamp + 1.0, frame=frame)
    sections = bind_cockpit_fields(bundle)
    assert "110.0" in sections["ai_decision"]["Objective"].value
    assert sections["market"]["Last Price"].value == "100.00"
    assert sections["market"]["Bid"].value == "UNWIRED"
    cards = bind_laboratory_cards(default_module_cards(), bundle)
    by_id = {c.spec.module_id: c for c in cards}
    assert by_id["objective"].status == "BOUND"
    assert "110.00" in by_id["objective"].outputs or "110.0" in by_id["objective"].outputs
    assert by_id["force"].status == "BOUND"
    assert by_id["execution"].status == "DISABLED"
    assert by_id["risk"].status == "N/A"


def test_loop_timing_system_health() -> None:
    timing = LoopTimingSnapshot(
        loop_ms=10.0,
        poll_ms=1.0,
        keyboard_ms=0.1,
        render_ms=1.0,
        sleep_ms=1.0,
        checkpoint_ms=2.0,
        initiative_checkpoint_ms=0.5,
        hierarchy_checkpoint_ms=1.5,
        logging_ms=3.0,
        start_time=1.0,
        end_time=2.0,
        poll_severity=TimingSeverity.OK,
        keyboard_severity=TimingSeverity.OK,
        render_severity=TimingSeverity.OK,
        sleep_severity=TimingSeverity.OK,
        checkpoint_severity=TimingSeverity.OK,
        initiative_checkpoint_severity=TimingSeverity.OK,
        hierarchy_checkpoint_severity=TimingSeverity.OK,
        logging_severity=TimingSeverity.SLOW,
        loop_severity=TimingSeverity.OK,
    )
    sections = bind_cockpit_fields(RuntimeBundle(now=3.0, loop_timing=timing))
    assert sections["system_health"]["Logger"].value == "SLOW"
    assert sections["system_health"]["Loop ms"].value == "10.00"
    cards = bind_laboratory_cards(default_module_cards(), RuntimeBundle(now=3.0, loop_timing=timing))
    by_id = {c.spec.module_id: c for c in cards}
    assert by_id["logger"].health == "SLOW"


def test_render_includes_provenance_marker() -> None:
    dash = DashboardState(
        market=LiveMarketView(symbol="MNQ", last_price=101.0, bid=100.75, ask=101.25)
    )
    text = render_cockpit(RuntimeBundle(now=time.time(), dashboard=dash), width=80)
    assert "| DashboardState  |" in text or "| DashboardState |" in text
    assert "DashboardState.market.last_price" not in text
    assert "WINDOW 1 · TRADING COCKPIT" in text


def test_events_capped_at_eight() -> None:
    dash = DashboardState(events=tuple(f"e{i}" for i in range(20)))
    sections = bind_cockpit_fields(RuntimeBundle(now=1.0, dashboard=dash))
    assert len(sections["recent_events"]) == 8


def test_lv_controller_read_only_latest() -> None:
    frame = _empty_frame()

    class Ctrl:
        latest = frame
        structural_transition_journal = ()

        def on_tick(self, *_a, **_k):
            raise AssertionError("on_tick must not be called")

        def evaluate_now(self):
            raise AssertionError("evaluate_now must not be called")

    from hotirjam_ai5.mission_control.app import MissionControlApp

    app = MissionControlApp(
        shell=MissionControlShell(),
        lv_controller=Ctrl(),
        sleep_fn=lambda _s: None,
        refresh_seconds=0.01,
    )
    text = app.render_once()
    assert "100.00" in text or "MNQ" in text


def test_mission_control_forbids_engine_calls_ast() -> None:
    for path in sorted(_MC_ROOT.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = None
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name in _FORBIDDEN_CALL_NAMES:
                    raise AssertionError(f"{path.name} calls {name}()")
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for prefix in _FORBIDDEN_IMPORT_PREFIXES:
                    assert not mod.startswith(prefix), f"{path.name} imports {mod}"


def test_shell_laboratory_render_with_bundle() -> None:
    frame = _empty_frame()
    shell = MissionControlShell(
        bundle=RuntimeBundle(now=frame.timestamp + 0.5, frame=frame)
    )
    shell.handle_key("2")
    text = shell.render()
    assert "WINDOW 2 · AI LABORATORY" in text
    assert "Status=BOUND" in text
