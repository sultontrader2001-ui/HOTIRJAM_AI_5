"""H-7.2A.1 Mission Control rendering stabilization tests."""

from __future__ import annotations

import time

from hotirjam_ai5.dashboard.models import DashboardState, LiveMarketView
from hotirjam_ai5.dashboard.terminal import TerminalDisplay
from hotirjam_ai5.mission_control.cockpit import render_cockpit
from hotirjam_ai5.mission_control.provenance import format_age
from hotirjam_ai5.mission_control.render_format import (
    dedupe_consecutive,
    fit_line,
    format_age_display,
    short_source,
    truncate,
)
from hotirjam_ai5.mission_control.runtime_bundle import RuntimeBundle
from hotirjam_ai5.mission_control.shell import MissionControlShell


def test_no_duplicate_consecutive_panel_rows() -> None:
    dash = DashboardState(
        market=LiveMarketView(symbol="MNQ", last_price=100.0, bid=99.75, ask=100.25)
    )
    text = render_cockpit(RuntimeBundle(now=time.time(), dashboard=dash), width=80)
    lines = text.splitlines()
    assert lines == dedupe_consecutive(lines)
    assert lines.count("WINDOW 1 · TRADING COCKPIT") == 1
    assert sum(1 for L in lines if L.strip().startswith("1 · MARKET")) == 1
    assert sum(1 for L in lines if L.strip().startswith("7 · RECENT EVENTS")) == 1


def test_cockpit_short_sources_only() -> None:
    dash = DashboardState(
        market=LiveMarketView(symbol="MNQ", last_price=100.0, bid=99.75, ask=100.25)
    )
    text = render_cockpit(RuntimeBundle(now=time.time(), dashboard=dash), width=80)
    assert "DashboardState.market" not in text
    assert "ValidatorFrame.objective" not in text
    assert "DashboardState" in text
    for family in ("ValidatorFrame", "DashboardState", "LoopTiming", "Journal"):
        assert short_source(f"{family}.foo.bar") == family


def test_impossible_ages_are_na() -> None:
    now = time.time()
    assert format_age_display(now, 1.0) == "N/A"
    assert format_age(now, 1.0) == "N/A"
    assert "29740657" not in format_age_display(now, 1.0)
    # Valid small delta
    assert format_age_display(now, now - 0.5).endswith("ms")
    assert format_age_display(now, now - 2.0).endswith("s")


def test_lines_never_exceed_width() -> None:
    dash = DashboardState(
        market=LiveMarketView(symbol="MNQ", last_price=100.0, bid=99.75, ask=100.25),
        events=("x" * 500,),
    )
    for width in (40, 60, 80, 120):
        text = render_cockpit(
            RuntimeBundle(now=time.time(), dashboard=dash), width=width
        )
        for line in text.splitlines():
            assert len(line) <= width, repr(line)


def test_truncate_ellipsis() -> None:
    assert truncate("ValidatorFrame.objective.nearest_high_price", 20).endswith("...")
    assert len(truncate("abcdef", 10)) == 6
    assert fit_line("a" * 100, 40) == ("a" * 37) + "..."


def test_resize_layout_stable() -> None:
    dash = DashboardState(
        market=LiveMarketView(symbol="MNQ", last_price=101.25, bid=101.0, ask=101.5)
    )
    bundle = RuntimeBundle(now=time.time(), dashboard=dash)
    shell = MissionControlShell(bundle=bundle)
    t40 = shell.render(width=40)
    t100 = shell.render(width=100)
    assert all(len(L) <= 40 for L in t40.splitlines())
    assert all(len(L) <= 100 for L in t100.splitlines())
    assert "TRADING COCKPIT" in t40
    assert "TRADING COCKPIT" in t100


def test_terminal_skips_identical_frame() -> None:
    writes: list[str] = []

    class Capture:
        def write(self, s: str) -> int:
            writes.append(s)
            return len(s)

        def flush(self) -> None:
            pass

        def isatty(self) -> bool:
            return False

    display = TerminalDisplay(stream=Capture(), ansi_supported=False)  # type: ignore[arg-type]
    display.prepare()
    frame = "line1\nline2"
    display.render_frame(frame)
    n1 = len(writes)
    display.render_frame(frame)
    n2 = len(writes)
    assert n2 == n1  # identical → no duplicate write
