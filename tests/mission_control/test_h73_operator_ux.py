"""H-7.3 Professional Operator UX certification."""

from __future__ import annotations

import ast
from pathlib import Path

from hotirjam_ai5.dashboard.terminal import TerminalDisplay
from hotirjam_ai5.mission_control.bind_operator import bind_operator_regions
from hotirjam_ai5.mission_control.models import MissionWindow
from hotirjam_ai5.mission_control.operator import render_operator
from hotirjam_ai5.mission_control.runtime_bundle import RuntimeBundle
from hotirjam_ai5.mission_control.shell import MissionControlShell


_MC_ROOT = Path(__file__).resolve().parents[2] / "src" / "hotirjam_ai5" / "mission_control"

_FORBIDDEN_IMPORT_PREFIXES = (
    "hotirjam_ai5.objective",
    "hotirjam_ai5.objective_diagnostics",
    "hotirjam_ai5.response",
    "hotirjam_ai5.continuation",
    "hotirjam_ai5.break_capability",
    "hotirjam_ai5.initiative",
    "hotirjam_ai5.physics",
    "hotirjam_ai5.liquidity",
    "hotirjam_ai5.market_state",
    "hotirjam_ai5.memory",
    "hotirjam_ai5.trade_decision",
    "hotirjam_ai5.decision_",
)


def test_operator_layout_regions_present() -> None:
    text = render_operator(RuntimeBundle(now=1.0), width=120, height=32)
    assert "HOTIRJAM AI 5" in text
    assert "TRADING COCKPIT" in text
    assert "AI LABORATORY" in text
    assert "DEVELOPER" in text
    for label in (
        "Current Objective",
        "Current Initiative",
        "Response",
        "Continuation",
        "Break Capability",
        "Confidence",
        "Current Setup",
        "Risk State",
        "Objective reasoning",
        "Initiative reasoning",
        "Response reasoning",
        "Module confidence",
        "Evidence",
        "Provenance",
        "Next trigger",
        "Loop time",
        "Checkpoint",
        "Feed health",
        "Runtime",
        "Memory",
        "Events",
        "Warnings",
        "Operator Messages",
        "No Trade reasons",
        "Certification",
        "System notices",
    ):
        assert label in text


def test_operator_header_fields() -> None:
    regions = bind_operator_regions(RuntimeBundle(now=1.0))
    for key in (
        "Product",
        "Session",
        "Symbol",
        "Last",
        "Market State",
        "AI Status",
        "System Health",
        "Decision",
        "Execution",
    ):
        assert key in regions["header"]


def test_operator_no_scroll_fixed_viewport() -> None:
    text = render_operator(RuntimeBundle(now=1.0), width=100, height=24)
    assert len(text.splitlines()) <= 24


def test_operator_no_duplicate_consecutive_rows() -> None:
    text = render_operator(RuntimeBundle(now=1.0), width=100, height=28)
    lines = text.splitlines()
    for a, b in zip(lines, lines[1:], strict=False):
        if a.strip() and b.strip() and a == b:
            # blank pad rows may match; content rows must not duplicate consecutively
            assert not any(tok in a for tok in ("Objective", "Initiative", "Loop time"))


def test_shell_defaults_to_operator() -> None:
    shell = MissionControlShell()
    assert shell.window is MissionWindow.OPERATOR
    text = shell.render(width=120, height=30)
    assert "TRADING COCKPIT" in text
    assert "AI LABORATORY" in text
    assert "DEVELOPER" in text


def test_operator_via_terminal_display_no_append() -> None:
    import io

    display = TerminalDisplay(stream=io.StringIO(), ansi_supported=False)
    shell = MissionControlShell()
    frame = shell.render(width=100, height=28)
    for _ in range(15):
        display.render_frame(frame)
    assert display.paint_count == 1
    assert display.skip_count == 14
    assert display._stream.getvalue().count("HOTIRJAM AI 5") == 1  # type: ignore[union-attr]


def test_operator_modules_forbid_engine_imports() -> None:
    for path in _MC_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                mod = node.module
                assert not any(
                    mod == p or mod.startswith(p + ".") for p in _FORBIDDEN_IMPORT_PREFIXES
                ), f"{path.name} imports {mod}"


def test_unwired_honest() -> None:
    text = render_operator(RuntimeBundle(now=1.0), width=120, height=32)
    assert "UNWIRED" in text or "N/A" in text
    assert "No published runtime" in text or "UNWIRED" in text
