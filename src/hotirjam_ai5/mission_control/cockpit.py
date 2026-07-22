"""Window 1 — Trading Cockpit layout (H-7.1). Presentation only."""

from __future__ import annotations

from hotirjam_ai5.mission_control.models import CockpitPanelState, default_cockpit_placeholders

_WIDTH = 78


def _rule(char: str = "-") -> str:
    return char * _WIDTH


def _kv_block(title: str, fields: dict[str, str]) -> list[str]:
    lines = [f"  {title}", "  " + ("." * (len(title) + 2))]
    width = max((len(k) for k in fields), default=8)
    for key, value in fields.items():
        lines.append(f"  {key.ljust(width)}  {value}")
    return lines


def render_cockpit(state: CockpitPanelState | None = None) -> str:
    """Render Trading Cockpit panels. Never fabricates market/AI values."""
    panel = state if state is not None else default_cockpit_placeholders()
    lines: list[str] = [
        "=" * _WIDTH,
        "WINDOW 1 · TRADING COCKPIT",
        "Read-only · Placeholders until bound · Never fabricate",
        _rule("="),
    ]
    lines.extend(_kv_block("1 · MARKET", panel.market))
    lines.append(_rule())
    lines.extend(_kv_block("2 · AI DECISION", panel.ai_decision))
    lines.append(_rule())
    lines.extend(_kv_block("3 · NEXT TRIGGER", panel.next_trigger))
    lines.append(_rule())
    lines.extend(_kv_block("4 · ACCOUNT", panel.account))
    lines.append(_rule())
    lines.extend(_kv_block("5 · SYSTEM HEALTH", panel.system_health))
    lines.append(_rule())
    lines.extend(_kv_block("6 · AI TIMELINE", panel.ai_timeline))
    lines.append(_rule())
    lines.append("  7 · RECENT EVENTS")
    lines.append("  " + ("." * 18))
    if panel.recent_events:
        for event in panel.recent_events[:8]:
            lines.append(f"  · {event}")
    else:
        lines.append("  · N/A")
    lines.append(_rule("="))
    lines.append("  Keys: 1 Cockpit  2 Laboratory  3 Developer  Q Quit  ? Help")
    return "\n".join(lines)
