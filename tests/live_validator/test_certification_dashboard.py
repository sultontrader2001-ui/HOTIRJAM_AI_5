"""Tests for the Live Certification Dashboard V2 (UI only)."""

from __future__ import annotations

import re

from hotirjam_ai5.live_validator.certification_dashboard import (
    AuditLog,
    MarketTelemetry,
    render_certification_dashboard,
)
from hotirjam_ai5.live_validator.pipeline import ArchitecturePipeline

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

# Left-to-right, top-to-bottom panel order in the two-column grid.
SECTIONS = (
    "MARKET",
    "OBJECTIVE ENGINE",
    "INITIATIVE ENGINE",
    "RESPONSE ENGINE",
    "CONTINUATION ENGINE",
    "BREAK CAPABILITY",
    "SYSTEM",
    "AUDIT LOG",
)

FIXED_WIDTH = 100  # resolved to 101 (2*panel + 3)


def _resolved_width(requested: int = FIXED_WIDTH) -> int:
    width = requested
    if (width - 3) % 2 != 0:
        width += 1
    return width


def _strip(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _empty_frame():
    return ArchitecturePipeline.empty_frame(timestamp=1_700_000_000.0)


def _full_frame():
    from hotirjam_ai5.initiative import OhlcCandle
    from hotirjam_ai5.objective import ConfirmedSwing

    candles = tuple(
        OhlcCandle(open=100 + i, high=100.5 + i, low=99.8 + i, close=100.4 + i, volume=10.0)
        for i in range(6)
    )
    return ArchitecturePipeline().evaluate(
        current_price=105.0,
        timestamp=1_700_000_000.0,
        candles=candles,
        confirmed_highs=(ConfirmedSwing(106.0, 70.0, confirmed_at=1.0),),
        confirmed_lows=(ConfirmedSwing(98.0, 65.0, confirmed_at=1.0),),
    )


def _render(frame=None, **kwargs) -> str:
    kwargs.setdefault("terminal_width", FIXED_WIDTH)
    kwargs.setdefault("use_color", False)
    return render_certification_dashboard(frame or _empty_frame(), **kwargs)


def test_all_sections_always_present() -> None:
    text = _render()
    position = -1
    for section in SECTIONS:
        found = text.find(section, position + 1)
        assert found > position, f"section {section} missing or out of order"
        position = found


def test_two_column_layout_uses_full_width() -> None:
    text = _render(terminal_width=FIXED_WIDTH)
    lines = text.splitlines()
    expected = _resolved_width(FIXED_WIDTH)
    assert all(len(_strip(line)) == expected for line in lines)
    assert any(line.count("+") == 3 for line in lines)
    assert any(line.count("|") == 3 for line in lines)


def test_equal_panel_widths() -> None:
    text = _render(terminal_width=FIXED_WIDTH)
    expected = _resolved_width(FIXED_WIDTH)
    panel = (expected - 3) // 2
    dual = [line for line in text.splitlines() if line.count("+") == 3][0]
    parts = dual.split("+")
    assert len(parts[1]) == len(parts[2]) == panel


def test_fixed_line_count_regardless_of_data() -> None:
    empty = _render(_empty_frame())
    full = _render(
        _full_frame(),
        feed_status="LIVE",
        market=MarketTelemetry(bid=104.75, ask=105.0, spread=0.25, tick_rate=12.0, latency_ms=42.0),
        uptime_seconds=3725.0,
    )
    assert len(empty.splitlines()) == len(full.splitlines())


def test_no_empty_fields_missing_data_shows_na() -> None:
    text = _strip(_render(_empty_frame()))
    assert "Bid" in text and "N/A" in text
    assert "Current High" in text
    assert "Major High" in text
    assert "Uptime" in text
    # Required labels always present.
    for label in ("Price", "Bid", "Ask", "Spread", "Tick Rate", "Latency"):
        assert label in text


def test_header_runtime_session_feed() -> None:
    text = _strip(
        _render(
            _full_frame(),
            feed_status="LIVE",
            uptime_seconds=3725.0,
        )
    )
    assert "HOTIRJAM AI 5" in text
    assert "LIVE CERTIFICATION DASHBOARD" in text
    assert "Runtime 01:02:05" in text
    assert "Session MNQ" in text
    assert "Feed LIVE" in text


def test_market_telemetry_rendered() -> None:
    text = _strip(
        _render(
            _full_frame(),
            feed_status="LIVE",
            market=MarketTelemetry(bid=104.75, ask=105.0, spread=0.25, tick_rate=12.0, latency_ms=42.0),
            uptime_seconds=3725.0,
        )
    )
    assert "105.00" in text
    assert "104.75" in text
    assert "0.25" in text
    assert "12.0 /s" in text
    assert "42 ms" in text


def test_objective_section_values() -> None:
    text = _strip(_render(_full_frame()))
    assert "Current High" in text and "106.00" in text
    assert "Current Low" in text and "98.00" in text
    assert "Distance" in text
    assert "H 4.0" in text and "L 28.0" in text
    assert "Status" in text and "COMPLETE" in text


def test_essential_fields_only_no_reason_noise() -> None:
    text = _render(_full_frame())
    assert "Reason" not in text
    assert "Absorption" not in text
    assert "Exhaustion" not in text
    assert "AI THINKING" not in text


def test_certification_badges_fixed_in_titles() -> None:
    empty = _strip(_render(_empty_frame()))
    # Default badges are N/A on each engine title row.
    assert empty.count("N/A") >= 5

    passed = _strip(
        _render(
            _empty_frame(),
            certifications={"objective": "PASS", "initiative": "FAIL"},
        )
    )
    assert "OBJECTIVE ENGINE" in passed and "PASS" in passed
    assert "INITIATIVE ENGINE" in passed and "FAIL" in passed
    # Line indices of engine titles stay stable.
    empty_lines = empty.splitlines()
    passed_lines = passed.splitlines()
    assert len(empty_lines) == len(passed_lines)
    obj_i = next(i for i, line in enumerate(empty_lines) if "OBJECTIVE ENGINE" in line)
    ini_i = next(i for i, line in enumerate(empty_lines) if "INITIATIVE ENGINE" in line)
    assert "PASS" in passed_lines[obj_i]
    assert "FAIL" in passed_lines[ini_i]


def test_colors_applied_when_enabled() -> None:
    plain = _render(_empty_frame(), use_color=False, certifications={"objective": "PASS"})
    colored = _render(_empty_frame(), use_color=True, certifications={"objective": "PASS"})
    assert "\033[32m" in colored  # green PASS
    assert "\033[90m" in colored  # gray N/A
    assert "\033[" not in plain
    # Visible layout width unchanged by color codes.
    assert len(_strip(colored).splitlines()[0]) == len(plain.splitlines()[0])


def test_audit_log_counts_and_recent_event() -> None:
    audit = AuditLog()
    audit.info("Validator started", timestamp=1_700_000_000.0)
    audit.warning("Feed STALE", timestamp=1_700_000_001.0)
    audit.error("Something failed", timestamp=1_700_000_002.0)
    text = _strip(_render(_empty_frame(), audit=audit))
    assert "INFO" in text
    assert "WARNING" in text
    assert "ERROR" in text
    # Most recent event only.
    assert "Something failed" in text
    assert "Validator started" not in text.split("Recent Event", 1)[1]


def test_audit_log_without_events_shows_na() -> None:
    text = _strip(_render(_empty_frame()))
    assert "Recent Event" in text
    assert "N/A" in text.split("Recent Event", 1)[1]


def test_decision_and_execution_always_disabled() -> None:
    text = _strip(_render(_full_frame()))
    assert "Decision" in text and "DISABLED" in text
    assert "Execution" in text and "DISABLED" in text


def test_panels_stay_aligned_across_rows() -> None:
    text = _render(_full_frame(), terminal_width=FIXED_WIDTH)
    content_rows = [line for line in text.splitlines() if line.startswith("|") and line.count("|") == 3]
    assert content_rows
    mid_col = content_rows[0].find("|", 1)
    assert mid_col > 0
    assert all(line.find("|", 1) == mid_col for line in content_rows)
