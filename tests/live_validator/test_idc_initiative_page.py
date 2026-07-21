"""H-6.6.3 IDC Initiative Engine page — read-only diagnostics."""

from __future__ import annotations

from dataclasses import replace

from hotirjam_ai5.initiative import (
    InitiativeEvidence,
    InitiativeSide,
    InitiativeSnapshot,
    InitiativeState,
)
from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.live_validator import (
    ArchitecturePipeline,
    IdcPage,
    LiveValidatorApp,
    LiveValidatorController,
    PresentationMode,
    render_idc,
)
from hotirjam_ai5.live_validator.idc_initiative import render_initiative_page


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


def _frame_with_initiative() -> object:
    initiative = InitiativeSnapshot(
        buyer_initiative=62.0,
        seller_initiative=20.0,
        dominant_side=InitiativeSide.BUYER,
        initiative_state=InitiativeState.DOMINANT,
        confidence=55.0,
        evidence=InitiativeEvidence(
            force=70.0,
            motion=60.0,
            pressure=50.0,
            liquidity=40.0,
            energy=45.0,
            context=25.0,
        ),
        reasons=("Buyer force present", "Dominant side BUYER"),
        timestamp=10.0,
    )
    frame = ArchitecturePipeline.empty_frame(timestamp=10.0)
    return replace(frame, current_price=100.0, initiative=initiative)


def test_initiative_page_layout_sections() -> None:
    frame = _frame_with_initiative()
    text = render_initiative_page(frame, feed_status="LIVE")  # type: ignore[arg-type]
    for section in (
        "INITIATIVE ENGINE",
        "Status",
        "Health",
        "Certification",
        "Last Evaluation",
        "CURRENT SNAPSHOT",
        "Buyer Initiative",
        "Seller Initiative",
        "Dominant Side",
        "Initiative State",
        "Confidence",
        "Timestamp",
        "LIFECYCLE",
        "Current State",
        "Allowed Next States",
        "EVIDENCE",
        "Force",
        "Motion",
        "Pressure",
        "Liquidity",
        "Energy",
        "Context",
        "REASONS",
        "TRANSITION JOURNAL",
        "WARNINGS",
        "Press Q to return",
    ):
        assert section in text
    assert "62.0" in text
    assert "BUYER" in text
    assert "DOMINANT" in text
    assert "HEALTHY" in text
    assert "LIVE" in text
    assert "NOT AVAILABLE" in text  # journal + certification
    assert "IMPLEMENTATION PENDING" not in text
    assert "Buyer force present" in text


def test_missing_frame_shows_not_available() -> None:
    text = render_initiative_page(None)
    assert "Missing Snapshot" in text
    assert "CRITICAL" in text
    assert "NOT AVAILABLE" in text


def test_low_confidence_and_missing_context_warnings() -> None:
    frame = _frame_with_initiative()
    weak = replace(
        frame.initiative,  # type: ignore[attr-defined]
        confidence=5.0,
        evidence=InitiativeEvidence(10.0, 10.0, 10.0, 10.0, 10.0, 0.0),
        initiative_state=InitiativeState.EMERGING,
    )
    frame = replace(frame, initiative=weak)  # type: ignore[arg-type]
    text = render_initiative_page(frame, feed_status="LIVE")  # type: ignore[arg-type]
    assert "Low Confidence" in text
    assert "Missing Context" in text
    assert "WARNING" in text


def test_transition_journal_not_invented() -> None:
    frame = _frame_with_initiative()
    text = render_initiative_page(frame)  # type: ignore[arg-type]
    journal = text.split("TRANSITION JOURNAL", 1)[1].split("WARNINGS", 1)[0]
    assert "NOT AVAILABLE" in journal


def test_initiative_page_never_calls_evaluate() -> None:
    controller = LiveValidatorController()
    before = controller.evaluations
    app = LiveValidatorApp(
        controller=controller,
        keyboard=_FakeKeyboard(["I", "2"]),  # type: ignore[arg-type]
        poll_seconds=0.01,
        refresh_seconds=0.01,
        sleep_fn=lambda _s: None,
    )
    app._poll_keyboard_toggle()
    app._poll_keyboard_toggle()
    assert app.presentation_mode is PresentationMode.IDC
    assert app.idc_page is IdcPage.INITIATIVE
    text = app.render_once()
    assert "INITIATIVE ENGINE" in text
    assert controller.evaluations == before


def test_acceptance_path_initiative_diagnostics() -> None:
    """Dashboard → I → 2 → Initiative → Q → IDC → Q → Dashboard."""
    app = LiveValidatorApp(
        controller=LiveValidatorController(),
        keyboard=_FakeKeyboard(["I", "2", "Q", "Q"]),  # type: ignore[arg-type]
        poll_seconds=0.01,
        refresh_seconds=0.01,
        sleep_fn=lambda _s: None,
    )
    app._poll_keyboard_toggle()
    app._poll_keyboard_toggle()
    assert app.idc_page is IdcPage.INITIATIVE
    text = app.render_once()
    assert "CURRENT SNAPSHOT" in text
    assert "IMPLEMENTATION PENDING" not in text
    app._poll_keyboard_toggle()
    assert app.idc_page is IdcPage.MENU
    app._poll_keyboard_toggle()
    assert app.presentation_mode is PresentationMode.DASHBOARD


def test_live_feed_continues_on_initiative_page() -> None:
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
        keyboard=_FakeKeyboard(["", "I", "2", "", ""]),  # type: ignore[arg-type]
        poll_seconds=0.01,
        refresh_seconds=0.01,
        sleep_fn=lambda _s: None,
    )
    app.run(max_frames=5)
    assert app.presentation_mode is PresentationMode.IDC
    assert app.idc_page is IdcPage.INITIATIVE
    assert app.feed_status() in {"LIVE", "STALE"}
    assert controller.evaluations >= 1


def test_render_idc_dispatches_initiative_page() -> None:
    frame = _frame_with_initiative()
    text = render_idc(IdcPage.INITIATIVE, frame=frame, feed_status="LIVE")  # type: ignore[arg-type]
    assert "Dominant Side" in text
    assert "BUYER" in text
