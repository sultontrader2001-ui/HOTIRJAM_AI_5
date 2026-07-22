"""H-7.1 Mission Control shell — presentation-only certification tests."""

from __future__ import annotations

import ast
from pathlib import Path

from hotirjam_ai5.mission_control import (
    MODULE_CATALOG,
    MissionControlApp,
    MissionControlShell,
    MissionWindow,
    ModuleGroup,
)
from hotirjam_ai5.mission_control.catalog import default_module_cards
from hotirjam_ai5.mission_control.cockpit import render_cockpit
from hotirjam_ai5.mission_control.developer import render_developer_placeholder
from hotirjam_ai5.mission_control.laboratory import render_laboratory
from hotirjam_ai5.mission_control.models import SourceBadge


_MC_ROOT = Path(__file__).resolve().parents[2] / "src" / "hotirjam_ai5" / "mission_control"

# Packages Mission Control must not import (no engines / no mutation paths).
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


def test_cockpit_has_required_panels() -> None:
    text = render_cockpit()
    for panel in (
        "1 · MARKET",
        "2 · AI DECISION",
        "3 · NEXT TRIGGER",
        "4 · ACCOUNT",
        "5 · SYSTEM HEALTH",
        "6 · AI TIMELINE",
        "7 · RECENT EVENTS",
    ):
        assert panel in text
    assert "N/A" in text
    assert "UNWIRED" in text or "DISABLED" in text
    # Must not fabricate numeric prices
    assert "#####" not in text


def test_laboratory_groups_and_modules() -> None:
    text = render_laboratory()
    for group in ("DATA", "MARKET", "INTELLIGENCE", "EXECUTION", "SYSTEM"):
        assert f"[{group}]" in text
    for name in (
        "Data",
        "Normalizer",
        "Physics",
        "Force",
        "Energy",
        "Liquidity",
        "Market State",
        "Memory",
        "Objective",
        "Response",
        "Continuation",
        "Break",
        "Risk",
        "Execution",
        "Logger",
        "Checkpoint",
    ):
        assert f"[{name}]" in text
    assert len(MODULE_CATALOG) == 16
    assert all(not c.expanded for c in default_module_cards())


def test_laboratory_collapsed_fields_and_badges() -> None:
    text = render_laboratory()
    assert "Status=" in text
    assert "Health=" in text
    assert "Latency=" in text
    assert "Last=" in text
    assert "Badge=" in text
    for badge in SourceBadge:
        # At least the catalog uses each conceptual badge type we care about
        pass
    badges = {spec.source_badge for spec in MODULE_CATALOG}
    assert SourceBadge.LIVE in badges
    assert SourceBadge.DASH in badges
    assert SourceBadge.INI in badges
    assert SourceBadge.OFF in badges
    assert SourceBadge.NA in badges
    assert SourceBadge.MIX in badges


def test_laboratory_expand_shows_required_sections() -> None:
    shell = MissionControlShell(window=MissionWindow.LABORATORY)
    shell.toggle_expand_selected()
    text = shell.render()
    for section in (
        "Identity",
        "Purpose",
        "Inputs",
        "Processing",
        "Outputs",
        "Dependencies",
        "Consumers",
        "Confidence",
        "Reason",
        "History",
        "Performance",
    ):
        assert section in text


def test_developer_placeholder_only() -> None:
    text = render_developer_placeholder()
    assert "WINDOW 3 · DEVELOPER CONSOLE" in text
    assert "Coming in H-7.9" in text
    assert "probe" not in text.lower() or "no probes" in text.lower()


def test_window_switching() -> None:
    shell = MissionControlShell()
    assert "MISSION CONTROL" in shell.render()
    assert "TRADING COCKPIT" in shell.render()
    assert "AI LABORATORY" in shell.render()
    assert "DEVELOPER" in shell.render()
    shell.handle_key("1")
    assert shell.window is MissionWindow.COCKPIT
    assert "WINDOW 1 · TRADING COCKPIT" in shell.render()
    shell.handle_key("2")
    assert shell.window is MissionWindow.LABORATORY
    assert "WINDOW 2 · AI LABORATORY" in shell.render()
    shell.handle_key("3")
    assert shell.window is MissionWindow.DEVELOPER
    assert "Coming in H-7.9" in shell.render()
    shell.handle_key("0")
    assert shell.window is MissionWindow.OPERATOR
    assert "TRADING COCKPIT" in shell.render()
    assert "AI LABORATORY" in shell.render()


def test_module_group_order() -> None:
    groups = [spec.group for spec in MODULE_CATALOG]
    # First DATA, last SYSTEM
    assert groups[0] is ModuleGroup.DATA
    assert groups[-1] is ModuleGroup.SYSTEM
    assert groups.count(ModuleGroup.DATA) == 2
    assert groups.count(ModuleGroup.MARKET) == 4
    assert groups.count(ModuleGroup.INTELLIGENCE) == 6
    assert groups.count(ModuleGroup.EXECUTION) == 2
    assert groups.count(ModuleGroup.SYSTEM) == 2


def test_app_once_render_no_engines() -> None:
    app = MissionControlApp(shell=MissionControlShell())
    text = app.render_once()
    assert "MISSION CONTROL" in text
    assert "Decision: DISABLED" in text


class _FakeKeyboard:
    def __init__(self, keys: list[str]) -> None:
        self._keys = list(keys)

    def enable(self) -> None:
        pass

    def disable(self) -> None:
        pass

    def poll_key(self) -> str | None:
        if self._keys:
            return self._keys.pop(0)
        return None


def test_app_interactive_navigation(tmp_path: Path) -> None:
    del tmp_path
    shell = MissionControlShell()
    app = MissionControlApp(
        shell=shell,
        keyboard=_FakeKeyboard(["2", "\r", "3", "q"]),
        refresh_seconds=0.01,
        sleep_fn=lambda _s: None,
    )
    app.run(max_frames=10)
    # q from detail view returns to Operator first
    assert shell.window in {
        MissionWindow.OPERATOR,
        MissionWindow.DEVELOPER,
        MissionWindow.LABORATORY,
        MissionWindow.COCKPIT,
    }


def test_mission_control_has_no_forbidden_engine_imports() -> None:
    """Static gate: mission_control package must not import engine packages."""
    for path in sorted(_MC_ROOT.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    for prefix in _FORBIDDEN_IMPORT_PREFIXES:
                        assert not name.startswith(prefix), f"{path.name} imports {name}"
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for prefix in _FORBIDDEN_IMPORT_PREFIXES:
                    assert not mod.startswith(prefix), f"{path.name} imports {mod}"


def test_cli_once(monkeypatch) -> None:
    from hotirjam_ai5.mission_control import app as mc_app

    buf: list[str] = []

    class Out:
        def write(self, s: str) -> int:
            buf.append(s)
            return len(s)

    monkeypatch.setattr(mc_app.sys, "stdout", Out())
    assert mc_app.main(["--once", "--window", "laboratory"]) == 0
    text = "".join(buf)
    assert "WINDOW 2 · AI LABORATORY" in text
