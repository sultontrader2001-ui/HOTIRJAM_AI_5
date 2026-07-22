"""Mission Control shell — window navigation and render dispatch (H-7.2).

Read-only consumer. Never allocates engines.
Never calls evaluate / calculate / recompute / predict / derive.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from hotirjam_ai5.mission_control.catalog import default_module_cards
from hotirjam_ai5.mission_control.cockpit import render_cockpit
from hotirjam_ai5.mission_control.developer import render_developer_placeholder
from hotirjam_ai5.mission_control.laboratory import cards_in_group_order, render_laboratory
from hotirjam_ai5.mission_control.models import (
    MissionWindow,
    ModuleCardState,
)
from hotirjam_ai5.mission_control.runtime_bundle import RuntimeBundle


class MissionControlShell:
    """In-memory presentation shell for three Mission Control windows."""

    def __init__(
        self,
        *,
        modules: list[ModuleCardState] | None = None,
        window: MissionWindow = MissionWindow.COCKPIT,
        bundle: RuntimeBundle | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._window = window
        self._clock = clock or time.time
        self._bundle = bundle if bundle is not None else RuntimeBundle(now=float(self._clock()))
        raw = modules if modules is not None else default_module_cards()
        self._modules = cards_in_group_order(raw)
        self._selected = 0
        self._help_visible = False

    @property
    def window(self) -> MissionWindow:
        return self._window

    @property
    def selected_index(self) -> int:
        return self._selected

    @property
    def modules(self) -> tuple[ModuleCardState, ...]:
        return tuple(self._modules)

    @property
    def bundle(self) -> RuntimeBundle:
        return self._bundle

    def set_bundle(self, bundle: RuntimeBundle) -> None:
        """Replace the read-only runtime bundle (already-existing objects only)."""
        self._bundle = bundle

    def set_window(self, window: MissionWindow) -> None:
        self._window = window
        self._help_visible = False

    def select_next(self) -> None:
        if not self._modules:
            return
        self._selected = (self._selected + 1) % len(self._modules)

    def select_prev(self) -> None:
        if not self._modules:
            return
        self._selected = (self._selected - 1) % len(self._modules)

    def toggle_expand_selected(self) -> None:
        if not self._modules:
            return
        card = self._modules[self._selected]
        card.expanded = not card.expanded

    def collapse_all(self) -> None:
        for card in self._modules:
            card.expanded = False

    def toggle_help(self) -> None:
        self._help_visible = not self._help_visible

    def handle_key(self, key: str) -> bool:
        """Handle one key. Returns False when the shell should quit."""
        if key in {"q", "Q"}:
            if self._window is MissionWindow.LABORATORY and any(
                c.expanded for c in self._modules
            ):
                self.collapse_all()
                return True
            return False
        if key == "1":
            self.set_window(MissionWindow.COCKPIT)
            return True
        if key == "2":
            self.set_window(MissionWindow.LABORATORY)
            return True
        if key == "3":
            self.set_window(MissionWindow.DEVELOPER)
            return True
        if key == "?":
            self.toggle_help()
            return True
        if self._window is MissionWindow.LABORATORY:
            if key in {"j", "J", "down", "\x1b[B"}:
                self.select_next()
                return True
            if key in {"k", "K", "up", "\x1b[A"}:
                self.select_prev()
                return True
            if key in {"\r", "\n", "e", "E"}:
                self.toggle_expand_selected()
                return True
        return True

    def render(self) -> str:
        # Refresh display_age clock without mutating runtime objects.
        self._bundle = RuntimeBundle(
            now=float(self._clock()),
            dashboard=self._bundle.dashboard,
            frame=self._bundle.frame,
            loop_timing=self._bundle.loop_timing,
            transition_summaries=self._bundle.transition_summaries,
        )
        header = self._chrome()
        if self._help_visible:
            body = self._help_text()
        elif self._window is MissionWindow.COCKPIT:
            body = render_cockpit(self._bundle)
        elif self._window is MissionWindow.LABORATORY:
            body = render_laboratory(
                self._modules,
                selected_index=self._selected,
                bundle=self._bundle,
            )
        else:
            body = render_developer_placeholder()
        return f"{header}\n{body}"

    def _chrome(self) -> str:
        w1 = "[1 Cockpit]" if self._window is MissionWindow.COCKPIT else " 1 Cockpit "
        w2 = (
            "[2 Laboratory]"
            if self._window is MissionWindow.LABORATORY
            else " 2 Laboratory "
        )
        w3 = (
            "[3 Developer]"
            if self._window is MissionWindow.DEVELOPER
            else " 3 Developer "
        )
        feed = "UNWIRED"
        if self._bundle.dashboard is not None:
            feed = self._bundle.dashboard.feed_health.feed_status.value
        elif self._bundle.frame is not None:
            feed = "BOUND"
        return (
            f"HOTIRJAM AI 5 · MISSION CONTROL  |  Feed: {feed}  |  Mode: OBSERVE\n"
            f"{w1}  {w2}  {w3}  |  Decision: DISABLED  |  Execution: DISABLED"
        )

    @staticmethod
    def _help_text() -> str:
        return "\n".join(
            [
                "HELP",
                "----",
                "1 / 2 / 3   Switch windows",
                "J K / arrows  Select Laboratory module",
                "Enter / E   Expand or collapse selected module",
                "Q           Collapse expansions, then quit",
                "?           Toggle this help",
                "",
                "Mission Control is a READ-ONLY consumer.",
                "It never evaluates engines or fabricates values.",
                "Every field carries provenance (src + age).",
            ]
        )
