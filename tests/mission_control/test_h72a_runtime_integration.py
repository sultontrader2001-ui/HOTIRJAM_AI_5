"""H-7.2A — Mission Control attaches to the live runner runtime (no second runtime)."""

from __future__ import annotations

import time
from pathlib import Path

from hotirjam_ai5.dashboard.app import DashboardApp, RunnerDisplayMode
from hotirjam_ai5.dashboard.controller import DashboardController
from hotirjam_ai5.dashboard.models import DashboardState
from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.live_validator import LiveValidatorApp, LiveValidatorController
from hotirjam_ai5.live_validator.pipeline import ArchitecturePipeline
from hotirjam_ai5.mission_control.bind_cockpit import bind_cockpit_fields
from hotirjam_ai5.mission_control.runtime_hub import (
    get_runtime_hub,
    reset_runtime_hub_for_tests,
)


def _tick(price: float, *, ts: float) -> LiveTick:
    return LiveTick(
        timestamp=ts,
        symbol="MNQ",
        last_price=price,
        bid=price - 0.25,
        ask=price,
        volume=1.0,
    )


class _FakeKeyboard:
    def enable(self) -> None:
        pass

    def disable(self) -> None:
        pass

    def poll_key(self) -> str | None:
        return None


def test_dashboard_runner_publishes_identical_state(tmp_path: Path) -> None:
    reset_runtime_hub_for_tests()
    controller = DashboardController(symbol="MNQ")
    app = DashboardApp(
        controller=controller,
        mission_control=True,
        keyboard=_FakeKeyboard(),
        sleep_fn=lambda _s: None,
        refresh_seconds=0.25,
        poll_seconds=0.05,
    )
    controller.start()
    controller.on_tick(_tick(100.5, ts=time.time()))
    text = app.render_once()
    hub = get_runtime_hub()
    assert hub.is_attached()
    assert hub.publisher == "DashboardApp"
    published = hub.dashboard
    assert isinstance(published, DashboardState)
    assert published is hub.read_bundle().dashboard
    assert published.market.last_price == 100.5
    assert "100.50" in text or "100.5" in text
    assert "MISSION CONTROL" in text
    assert app.display_mode is RunnerDisplayMode.MISSION_CONTROL
    # One snapshot path: MC did not create a second DashboardState.
    assert hub.publish_count >= 1


def test_mission_control_does_not_call_controller_snapshot() -> None:
    reset_runtime_hub_for_tests()
    calls = {"snapshot": 0}

    class Guard(DashboardController):
        def snapshot(self) -> DashboardState:  # type: ignore[override]
            calls["snapshot"] += 1
            return super().snapshot()

    controller = Guard(symbol="MNQ")
    controller.start()
    controller.on_tick(_tick(101.0, ts=time.time()))
    # Runner may call snapshot once.
    app = DashboardApp(
        controller=controller,
        mission_control=True,
        keyboard=_FakeKeyboard(),
        sleep_fn=lambda _s: None,
    )
    before = calls["snapshot"]
    app.render_once()
    after = calls["snapshot"]
    assert after == before + 1  # exactly one runner snapshot
    # Binding reads published state only.
    sections = bind_cockpit_fields(get_runtime_hub().read_bundle())
    assert sections["market"]["Last Price"].value.startswith("101")


def test_live_validator_publishes_frame(tmp_path: Path) -> None:
    reset_runtime_hub_for_tests()
    controller = LiveValidatorController(
        pipeline=ArchitecturePipeline(
            hierarchy_checkpoint_path=tmp_path / "h.json",
            initiative_checkpoint_path=tmp_path / "i.json",
        )
    )
    app = LiveValidatorApp(
        controller=controller,
        keyboard=_FakeKeyboard(),  # type: ignore[arg-type]
        mission_control=True,
        sleep_fn=lambda _s: None,
    )
    controller.on_tick(_tick(99.75, ts=1.0))
    text = app.render_once()
    hub = get_runtime_hub()
    assert hub.is_attached()
    assert hub.publisher == "LiveValidatorApp"
    assert hub.frame is controller.latest
    assert hub.frame is not None
    assert hub.frame.current_price == 99.75
    assert "MISSION CONTROL" in text
    assert "Objective" in text or "OBJECTIVE" in text or "99.75" in text


def test_hub_read_bundle_no_duplication() -> None:
    reset_runtime_hub_for_tests()
    controller = DashboardController(symbol="MNQ")
    controller.start()
    controller.on_tick(_tick(102.0, ts=time.time()))
    state = controller.snapshot()
    hub = get_runtime_hub()
    hub.publish_dashboard(state)
    b1 = hub.read_bundle()
    b2 = hub.read_bundle()
    assert b1.dashboard is state
    assert b2.dashboard is state
    assert b1.dashboard is b2.dashboard


def test_standalone_mc_without_hub_stays_unwired() -> None:
    reset_runtime_hub_for_tests()
    from hotirjam_ai5.mission_control.shell import MissionControlShell

    text = MissionControlShell().render()
    assert "UNWIRED" in text or "N/A" in text
