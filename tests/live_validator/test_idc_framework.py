"""H-6.6.1 Internal Diagnostics Console — framework only."""

from __future__ import annotations

from hotirjam_ai5.live_data.tick import LiveTick
from hotirjam_ai5.live_validator import (
    IdcPage,
    LiveValidatorApp,
    LiveValidatorController,
    PresentationMode,
    render_idc,
    render_idc_main_menu,
)
from hotirjam_ai5.live_validator.idc import idc_page_for_key


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
        self.enabled = 0
        self.disabled = 0

    def enable(self) -> None:
        self.enabled += 1

    def disable(self) -> None:
        self.disabled += 1

    def poll_key(self) -> str | None:
        if self._pending:
            return self._pending.pop(0)
        if self._batches:
            self._pending = list(self._batches.pop(0))
        return None


def test_idc_main_menu_content() -> None:
    text = render_idc_main_menu()
    assert "HOTIRJAM AI 5" in text
    assert "Internal Diagnostics Console" in text
    assert "Read Only" in text
    assert "Engineering Console" in text
    assert "1  Objective Engine" in text
    assert "2  Initiative Engine" in text
    assert "3  Response Engine" in text
    assert "4  Continuation Engine" in text
    assert "5  Break Capability" in text
    assert "6  Market State" in text
    assert "7  Physics" in text
    assert "8  Structural Memory" in text
    assert "9  Performance" in text
    assert "A  Live Audit" in text
    assert "B  Certification" in text
    assert "W  Warnings" in text
    assert "Q  Return Dashboard" in text


def test_idc_placeholders_for_every_page() -> None:
    expected = {
        IdcPage.RESPONSE: "RESPONSE ENGINE",
        IdcPage.CONTINUATION: "CONTINUATION ENGINE",
        IdcPage.BREAK_CAPABILITY: "BREAK CAPABILITY",
        IdcPage.MARKET_STATE: "MARKET STATE",
        IdcPage.PHYSICS: "PHYSICS",
        IdcPage.STRUCTURAL_MEMORY: "STRUCTURAL MEMORY",
        IdcPage.LIVE_AUDIT: "LIVE AUDIT",
        IdcPage.CERTIFICATION: "CERTIFICATION",
        IdcPage.WARNINGS: "WARNINGS",
    }
    for page, title in expected.items():
        text = render_idc(page)
        assert title in text
        assert "IMPLEMENTATION PENDING" in text
        assert "Press Q to return" in text


def test_objective_page_is_not_placeholder() -> None:
    text = render_idc(IdcPage.OBJECTIVE)
    assert "OBJECTIVE ENGINE" in text
    assert "IMPLEMENTATION PENDING" not in text
    assert "CURRENT SNAPSHOT" in text
    assert "NOT AVAILABLE" in text
    assert "Press Q to return" in text


def test_initiative_page_is_not_placeholder() -> None:
    text = render_idc(IdcPage.INITIATIVE)
    assert "INITIATIVE ENGINE" in text
    assert "IMPLEMENTATION PENDING" not in text
    assert "Buyer Initiative" in text
    assert "Press Q to return" in text


def test_performance_page_is_not_placeholder() -> None:
    text = render_idc(IdcPage.PERFORMANCE)
    assert "PERFORMANCE" in text
    assert "IMPLEMENTATION PENDING" not in text
    assert "MAIN LOOP" in text
    assert "NOT AVAILABLE" in text
    assert "Press Q to return" in text


def test_menu_keys_map_to_pages() -> None:
    assert idc_page_for_key("1") is IdcPage.OBJECTIVE
    assert idc_page_for_key("5") is IdcPage.BREAK_CAPABILITY
    assert idc_page_for_key("a") is IdcPage.LIVE_AUDIT
    assert idc_page_for_key("B") is IdcPage.CERTIFICATION
    assert idc_page_for_key("w") is IdcPage.WARNINGS
    assert idc_page_for_key("q") is None


def test_acceptance_navigation_path() -> None:
    """Dashboard → I → Menu → 1 → Objective page → Q → Menu → Q → Dashboard."""
    app = LiveValidatorApp(
        controller=LiveValidatorController(),
        keyboard=_FakeKeyboard(["I", "1", "Q", "Q"]),  # type: ignore[arg-type]
        poll_seconds=0.01,
        refresh_seconds=0.01,
        sleep_fn=lambda _s: None,
    )
    assert app.presentation_mode is PresentationMode.DASHBOARD

    assert app._poll_keyboard_toggle() is True
    assert app.presentation_mode is PresentationMode.IDC
    assert app.idc_page is IdcPage.MENU
    assert "Internal Diagnostics Console" in app.render_once()

    assert app._poll_keyboard_toggle() is True
    assert app.idc_page is IdcPage.OBJECTIVE
    text = app.render_once()
    assert "OBJECTIVE ENGINE" in text
    assert "CURRENT SNAPSHOT" in text
    assert "IMPLEMENTATION PENDING" not in text

    assert app._poll_keyboard_toggle() is True
    assert app.presentation_mode is PresentationMode.IDC
    assert app.idc_page is IdcPage.MENU

    assert app._poll_keyboard_toggle() is True
    assert app.presentation_mode is PresentationMode.DASHBOARD
    assert app.idc_page is IdcPage.MENU


def test_idc_does_not_call_evaluate() -> None:
    controller = LiveValidatorController()
    before = controller.evaluations
    app = LiveValidatorApp(
        controller=controller,
        keyboard=_FakeKeyboard([]),  # type: ignore[arg-type]
    )
    app.enter_idc()
    app.render_once()
    app._idc_page = IdcPage.INITIATIVE
    app.render_once()
    assert controller.evaluations == before


def test_idc_preserves_feed_and_runtime() -> None:
    class FakeIngress:
        def __init__(self) -> None:
            self._ts = 0.0

        def poll(self) -> tuple[LiveTick, ...]:
            self._ts += 1.0
            return (_tick(100.0 + self._ts * 0.25, ts=self._ts),)

    controller = LiveValidatorController()
    keyboard = _FakeKeyboard(["", "I", "1", "Q", "Q"])
    app = LiveValidatorApp(
        controller=controller,
        ingress=FakeIngress(),  # type: ignore[arg-type]
        poll_seconds=0.01,
        refresh_seconds=0.01,
        sleep_fn=lambda _s: None,
        keyboard=keyboard,  # type: ignore[arg-type]
    )
    code = app.run(max_frames=5)
    assert code == 0
    assert app.presentation_mode is PresentationMode.DASHBOARD
    assert app.feed_status() in {"LIVE", "STALE"}
    assert controller.evaluations >= 1
    assert keyboard.enabled == 1
    assert keyboard.disabled == 1


def test_developer_view_independent_of_idc() -> None:
    app = LiveValidatorApp(controller=LiveValidatorController())
    app.toggle_developer_mode()
    assert app.developer_mode is True
    assert app.presentation_mode is PresentationMode.DASHBOARD
    app.enter_idc()
    assert app.presentation_mode is PresentationMode.IDC
    # D is ignored while IDC is open.
    app.toggle_developer_mode()
    assert app.presentation_mode is PresentationMode.IDC
    app.exit_idc()
    assert app.presentation_mode is PresentationMode.DASHBOARD
    assert app.developer_mode is False
