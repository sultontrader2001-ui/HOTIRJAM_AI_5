"""H-6.6.2 IDC Objective Engine page — read-only diagnostics."""

from __future__ import annotations

from dataclasses import replace

from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.live_validator import (
    ArchitecturePipeline,
    IdcPage,
    LiveValidatorApp,
    LiveValidatorController,
    PresentationMode,
    render_idc,
)
from hotirjam_ai5.live_validator.diagnostic_projection import derive_diagnostic_log
from hotirjam_ai5.live_validator.idc_objective import render_objective_page
from hotirjam_ai5.objective import ObjectivePersistenceState, ObjectiveSnapshot
from hotirjam_ai5.objective_diagnostics import (
    CandidateCategory,
    LifecycleState,
    ObjectiveAuditReport,
    SwingDiagnostic,
    SwingSide,
)
from hotirjam_ai5.objective_diagnostics.persistent_hierarchy import StructuralTransition


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
    def __init__(self, batches: list[str]) -> None:
        self._batches = list(batches)
        self._pending: list[str] = list(self._batches.pop(0)) if self._batches else []

    def enable(self) -> None:
        pass

    def disable(self) -> None:
        pass

    def poll_key(self) -> str | None:
        if self._pending:
            return self._pending.pop(0)
        if self._batches:
            self._pending = list(self._batches.pop(0))
        return None


def _diag(
    *,
    side: SwingSide,
    price: float,
    lifecycle: LifecycleState = LifecycleState.ACTIVE,
) -> SwingDiagnostic:
    return SwingDiagnostic(
        swing_id=1 if side is SwingSide.HIGH else 2,
        side=side,
        price=price,
        confirmed_at=1.0,
        distance_ticks=4.0,
        current_strength=80.0,
        parent_swing_id=None,
        hierarchy_depth=0,
        persistence=70.0,
        prominence=8.0,
        lifecycle=lifecycle,
        category=CandidateCategory.MAJOR,
        eligible=True,
        rejection_reasons=("Selected nearest eligible MAJOR",),
        challenge_state="NONE",
        challenge_evidence=(),
        transition_cause="ACTIVATED",
        transition_time=1.5,
    )


def _frame_with_objectives() -> object:
    high = _diag(side=SwingSide.HIGH, price=110.0)
    low = _diag(side=SwingSide.LOW, price=90.0, lifecycle=LifecycleState.CHALLENGED)
    report = ObjectiveAuditReport(
        timestamp=10.0,
        current_price=100.0,
        tick_size=0.25,
        highs=(high,),
        lows=(low,),
        summary_lines=("Both sides present",),
        hierarchy_version=3,
        registry_size=2,
        transition_count=1,
        checkpoint_version=2,
    )
    objective = ObjectiveSnapshot(
        nearest_high_price=110.0,
        nearest_high_distance_ticks=40.0,
        nearest_high_strength=80.0,
        nearest_low_price=90.0,
        nearest_low_distance_ticks=40.0,
        nearest_low_strength=80.0,
        current_price=100.0,
        timestamp=10.0,
        high_state=ObjectivePersistenceState.PERSISTED,
        low_state=ObjectivePersistenceState.PERSISTED,
    )
    frame = ArchitecturePipeline.empty_frame(timestamp=10.0)
    return replace(
        frame,
        current_price=100.0,
        objective=objective,
        objective_diagnostics=report,
        diagnostic_log=derive_diagnostic_log(report, objective),
    )


def test_objective_page_layout_sections() -> None:
    frame = _frame_with_objectives()
    text = render_objective_page(frame, feed_status="LIVE", transitions=())  # type: ignore[arg-type]
    for section in (
        "OBJECTIVE ENGINE",
        "Status",
        "Health",
        "Certification",
        "Last Evaluation",
        "SUMMARY (diagnostic_log)",
        "CURRENT SNAPSHOT",
        "Current High",
        "Current Low",
        "Distance High",
        "Distance Low",
        "Calculation State",
        "LIFECYCLE",
        "DETAIL (objective_diagnostics)",
        "EVIDENCE",
        "REASONS",
        "TRANSITION JOURNAL",
        "WARNINGS",
        "Press Q to return",
    ):
        assert section in text
    assert "110.00" in text
    assert "90.00" in text
    assert "READY" in text
    assert "HEALTHY" in text
    assert "LIVE" in text
    assert "NOT AVAILABLE" in text  # certification unset
    assert "IMPLEMENTATION PENDING" not in text


def test_missing_fields_show_not_available() -> None:
    frame = ArchitecturePipeline.empty_frame(timestamp=1.0)
    text = render_objective_page(frame, transitions=None)
    assert "Missing Diagnostics" in text
    assert "NOT AVAILABLE" in text
    assert "WARNING" in text or "CRITICAL" in text


def test_transition_journal_renders_existing_entries() -> None:
    frame = _frame_with_objectives()
    journal = (
        StructuralTransition(
            sequence=1,
            timestamp=1_700_000_000.0,
            cause="PRICE_TRADE_THROUGH",
            swing_id=2,
            old_state={"lifecycle": "ACTIVE"},
            new_state={"lifecycle": "CHALLENGED"},
            evidence={},
        ),
    )
    text = render_objective_page(frame, transitions=journal)  # type: ignore[arg-type]
    assert "PRICE_TRADE_THROUGH" in text
    assert "ACTIVE → CHALLENGED" in text


def test_objective_page_never_calls_evaluate() -> None:
    controller = LiveValidatorController()
    before = controller.evaluations
    app = LiveValidatorApp(
        controller=controller,
        keyboard=_FakeKeyboard(["I", "1"]),  # type: ignore[arg-type]
        poll_seconds=0.01,
        refresh_seconds=0.01,
        sleep_fn=lambda _s: None,
    )
    app._poll_keyboard_toggle()
    app._poll_keyboard_toggle()
    assert app.presentation_mode is PresentationMode.IDC
    assert app.idc_page is IdcPage.OBJECTIVE
    text = app.render_once()
    assert "OBJECTIVE ENGINE" in text
    assert controller.evaluations == before


def test_acceptance_path_objective_diagnostics() -> None:
    """Dashboard → I → IDC → 1 → Objective → Q → IDC → Q → Dashboard."""
    controller = LiveValidatorController()
    app = LiveValidatorApp(
        controller=controller,
        keyboard=_FakeKeyboard(["I", "1", "Q", "Q"]),  # type: ignore[arg-type]
        poll_seconds=0.01,
        refresh_seconds=0.01,
        sleep_fn=lambda _s: None,
    )
    app._poll_keyboard_toggle()
    assert app.presentation_mode is PresentationMode.IDC
    app._poll_keyboard_toggle()
    assert app.idc_page is IdcPage.OBJECTIVE
    text = app.render_once()
    assert "CURRENT SNAPSHOT" in text
    assert "IMPLEMENTATION PENDING" not in text
    app._poll_keyboard_toggle()
    assert app.idc_page is IdcPage.MENU
    app._poll_keyboard_toggle()
    assert app.presentation_mode is PresentationMode.DASHBOARD


def test_live_feed_continues_on_objective_page() -> None:
    class FakeIngress:
        def __init__(self) -> None:
            self._ts = 0.0

        def poll(self) -> tuple[LiveTick, ...]:
            self._ts += 1.0
            return (_tick(100.0 + self._ts * 0.25, ts=self._ts),)

    controller = LiveValidatorController()
    app = LiveValidatorApp(
        controller=controller,
        ingress=FakeIngress(),  # type: ignore[arg-type]
        keyboard=_FakeKeyboard(["", "I", "1", "", ""]),  # type: ignore[arg-type]
        poll_seconds=0.01,
        refresh_seconds=0.01,
        sleep_fn=lambda _s: None,
    )
    app.run(max_frames=5)
    assert app.presentation_mode is PresentationMode.IDC
    assert app.idc_page is IdcPage.OBJECTIVE
    assert app.feed_status() in {"LIVE", "STALE"}
    assert controller.evaluations >= 1
    text = app.render_once()
    assert "OBJECTIVE ENGINE" in text
    assert "LIVE" in text or "STALE" in text or "WAITING" in text


def test_render_idc_dispatches_objective_page() -> None:
    frame = _frame_with_objectives()
    text = render_idc(IdcPage.OBJECTIVE, frame=frame, feed_status="LIVE", transitions=())  # type: ignore[arg-type]
    assert "Calculation State" in text
    assert "READY" in text
