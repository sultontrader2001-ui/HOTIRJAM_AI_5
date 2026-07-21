"""Tests for the Live Certification Dashboard (Sprint 1 — UI only)."""

from __future__ import annotations

from hotirjam_ai5.live_validator.certification_dashboard import (
    AuditLog,
    MarketTelemetry,
    render_certification_dashboard,
)
from hotirjam_ai5.live_validator.pipeline import ArchitecturePipeline

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


def test_all_sections_always_present() -> None:
    text = render_certification_dashboard(_empty_frame())
    position = -1
    for section in SECTIONS:
        found = text.find(section, position + 1)
        assert found > position, f"section {section} missing or out of order"
        position = found


def test_fixed_line_count_regardless_of_data() -> None:
    empty = render_certification_dashboard(_empty_frame())
    full = render_certification_dashboard(
        _full_frame(),
        feed_status="LIVE",
        market=MarketTelemetry(bid=104.75, ask=105.0, spread=0.25, tick_rate=12.0, latency_ms=42.0),
        uptime_seconds=3725.0,
    )
    assert len(empty.splitlines()) == len(full.splitlines())


def test_no_empty_fields_missing_data_shows_na() -> None:
    text = render_certification_dashboard(_empty_frame())
    lines = text.splitlines()
    assert all(line.strip() for line in lines), "no line may be empty"
    # Unavailable values must render as N/A.
    assert "Bid               N/A" in text
    assert "Ask               N/A" in text
    assert "Spread            N/A" in text
    assert "Tick Rate         N/A" in text
    assert "Latency           N/A" in text
    assert "Current High      N/A" in text
    assert "Major High        N/A" in text
    assert "Major Low         N/A" in text
    assert "Uptime            N/A" in text


def test_market_telemetry_rendered() -> None:
    text = render_certification_dashboard(
        _full_frame(),
        feed_status="LIVE",
        market=MarketTelemetry(bid=104.75, ask=105.0, spread=0.25, tick_rate=12.0, latency_ms=42.0),
        uptime_seconds=3725.0,
    )
    assert "Symbol            MNQ" in text
    assert "Price             105.00" in text
    assert "Bid               104.75" in text
    assert "Ask               105.00" in text
    assert "Spread            0.25" in text
    assert "Tick Rate         12.0 /s" in text
    assert "Feed              LIVE" in text
    assert "Latency           42 ms" in text
    assert "Uptime            01:02:05" in text


def test_objective_section_values() -> None:
    text = render_certification_dashboard(_full_frame())
    assert "Current High      106.00" in text
    assert "Current Low       98.00" in text
    assert "Distance High     4.0" in text
    assert "Distance Low      28.0" in text
    assert "Objective State   COMPLETE" in text


def test_certification_defaults_na_and_fixed_position() -> None:
    empty = render_certification_dashboard(_empty_frame())
    cert_lines = [
        (i, line)
        for i, line in enumerate(empty.splitlines())
        if line.startswith("Certification")
    ]
    assert len(cert_lines) == 5
    assert all(line == "Certification     N/A" for _, line in cert_lines)

    passed = render_certification_dashboard(
        _empty_frame(),
        certifications={"objective": "PASS", "initiative": "FAIL"},
    )
    pass_lines = [
        (i, line)
        for i, line in enumerate(passed.splitlines())
        if line.startswith("Certification")
    ]
    # PASS/FAIL replace N/A at the same line index and column.
    assert [i for i, _ in pass_lines] == [i for i, _ in cert_lines]
    assert pass_lines[0][1] == "Certification     PASS"
    assert pass_lines[1][1] == "Certification     FAIL"
    assert pass_lines[2][1] == "Certification     N/A"


def test_values_aligned_in_columns() -> None:
    text = render_certification_dashboard(_full_frame(), feed_status="LIVE")
    for line in text.splitlines():
        if line.startswith(("Symbol", "Price", "Confidence", "Certification", "Decision")):
            label = line[:18]
            assert label == label.rstrip().ljust(18)
            assert line[18] != " "


def test_audit_log_counts_and_recent_events() -> None:
    audit = AuditLog()
    audit.info("Validator started", timestamp=1_700_000_000.0)
    audit.warning("Feed STALE", timestamp=1_700_000_001.0)
    audit.error("Something failed", timestamp=1_700_000_002.0)
    text = render_certification_dashboard(_empty_frame(), audit=audit)
    assert "INFO              1" in text
    assert "WARNING           1" in text
    assert "ERROR             1" in text
    assert "Validator started" in text
    assert "Feed STALE" in text
    assert "Something failed" in text


def test_audit_log_without_events_shows_na_rows() -> None:
    text = render_certification_dashboard(_empty_frame())
    tail = text.split("Recent Events", 1)[1]
    assert tail.count("N/A") >= 5


def test_decision_and_execution_always_disabled() -> None:
    text = render_certification_dashboard(_full_frame())
    assert "Decision          DISABLED" in text
    assert "Execution         DISABLED" in text
