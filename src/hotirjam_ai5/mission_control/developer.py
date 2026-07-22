"""Window 3 — Developer Console placeholder (H-7.2A.1 width-safe)."""

from __future__ import annotations

from hotirjam_ai5.mission_control.render_format import (
    clamp_lines,
    fit_line,
    terminal_width,
)


def render_developer_placeholder(*, width: int | None = None) -> str:
    """Single placeholder page. Nothing else until H-7.9."""
    panel_width = max(40, int(width) if width is not None else terminal_width())
    lines = [
        "=" * panel_width,
        "WINDOW 3 · DEVELOPER CONSOLE",
        "=" * panel_width,
        "",
        "  Coming in H-7.9",
        "",
        "  N/A — placeholder only",
        "  UNWIRED — no probes bound",
        "",
        "  Full provenance and raw dumps land here later.",
        "  Cockpit stays minimal; Laboratory shows module detail.",
        "",
        "=" * panel_width,
        "  Keys: 1 Cockpit  2 Laboratory  3 Developer  Q Quit",
    ]
    return "\n".join(clamp_lines([fit_line(x, panel_width) for x in lines], panel_width))
