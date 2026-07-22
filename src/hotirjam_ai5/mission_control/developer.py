"""Window 3 — Developer Console placeholder (H-7.1)."""

from __future__ import annotations

_WIDTH = 78


def render_developer_placeholder() -> str:
    """Single placeholder page. Nothing else until H-7.9."""
    lines = [
        "=" * _WIDTH,
        "WINDOW 3 · DEVELOPER CONSOLE",
        "=" * _WIDTH,
        "",
        "  Coming in H-7.9",
        "",
        "  N/A — placeholder only",
        "  UNWIRED — no probes bound",
        "",
        "  This window will host raw dumps, journals, loop timings,",
        "  and certification fingerprints. Not available in H-7.1.",
        "",
        "=" * _WIDTH,
        "  Keys: 1 Cockpit  2 Laboratory  3 Developer  Q Quit",
    ]
    return "\n".join(lines)
