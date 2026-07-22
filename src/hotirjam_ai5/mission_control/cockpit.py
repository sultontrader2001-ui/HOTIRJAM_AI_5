"""Window 1 — Trading Cockpit layout with provenance (H-7.2)."""

from __future__ import annotations

from hotirjam_ai5.mission_control.bind_cockpit import bind_cockpit_fields
from hotirjam_ai5.mission_control.provenance import ProvenancedField
from hotirjam_ai5.mission_control.runtime_bundle import RuntimeBundle

_WIDTH = 78


def _rule(char: str = "-") -> str:
    return char * _WIDTH


def _section(title: str, fields: dict[str, ProvenancedField]) -> list[str]:
    lines = [f"  {title}", "  " + ("." * max(12, len(title)))]
    width = max((len(k) for k in fields), default=12)
    for key, field in fields.items():
        lines.append(field.line(key, width=width))
    return lines


def render_cockpit(bundle: RuntimeBundle | None = None) -> str:
    """Render Trading Cockpit from a read-only runtime bundle."""
    if bundle is None:
        import time

        bundle = RuntimeBundle(now=time.time())
    sections = bind_cockpit_fields(bundle)
    lines: list[str] = [
        "=" * _WIDTH,
        "WINDOW 1 · TRADING COCKPIT",
        "Read-only · Provenanced fields · Never fabricate",
        _rule("="),
    ]
    lines.extend(_section("1 · MARKET", sections["market"]))
    lines.append(_rule())
    lines.extend(_section("2 · AI DECISION", sections["ai_decision"]))
    lines.append(_rule())
    lines.extend(_section("3 · NEXT TRIGGER", sections["next_trigger"]))
    lines.append(_rule())
    lines.extend(_section("4 · ACCOUNT", sections["account"]))
    lines.append(_rule())
    lines.extend(_section("5 · SYSTEM HEALTH", sections["system_health"]))
    lines.append(_rule())
    lines.extend(_section("6 · AI TIMELINE", sections["ai_timeline"]))
    lines.append(_rule())
    lines.extend(_section("7 · RECENT EVENTS", sections["recent_events"]))
    lines.append(_rule("="))
    lines.append("  Keys: 1 Cockpit  2 Laboratory  3 Developer  Q Quit  ? Help")
    return "\n".join(lines)
