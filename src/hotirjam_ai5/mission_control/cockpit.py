"""Window 1 — Trading Cockpit layout (H-7.2A.1 render stabilization)."""

from __future__ import annotations

from hotirjam_ai5.mission_control.bind_cockpit import bind_cockpit_fields
from hotirjam_ai5.mission_control.provenance import ProvenancedField
from hotirjam_ai5.mission_control.render_format import (
    clamp_lines,
    dedupe_consecutive,
    fit_line,
    format_age_display,
    short_source,
    terminal_width,
    truncate,
)
from hotirjam_ai5.mission_control.runtime_bundle import RuntimeBundle


def _rule(width: int, char: str = "-") -> str:
    return char * width


def _cockpit_row(
    label: str,
    field: ProvenancedField,
    *,
    label_width: int,
    panel_width: int,
    now: float,
) -> str:
    """Trader line: value + short source family + safe age. No full paths."""
    src = short_source(field.source_object)
    age = format_age_display(now, field.timestamp)
    value_budget = max(8, panel_width - label_width - len(src) - len(age) - 12)
    value = truncate(field.value, value_budget)
    line = f"  {label.ljust(label_width)}  {value}  | {src}  | {age}"
    return fit_line(line, panel_width)


def _section(
    title: str,
    fields: dict[str, ProvenancedField],
    *,
    panel_width: int,
    now: float,
) -> list[str]:
    lines = [f"  {title}", "  " + ("." * min(panel_width - 2, max(12, len(title))))]
    label_width = min(14, max((len(k) for k in fields), default=8))
    for key, field in fields.items():
        lines.append(
            _cockpit_row(
                key,
                field,
                label_width=label_width,
                panel_width=panel_width,
                now=now,
            )
        )
    return lines


def render_cockpit(
    bundle: RuntimeBundle | None = None,
    *,
    width: int | None = None,
) -> str:
    """Render Trading Cockpit once — minimal trader view, no overflow."""
    if bundle is None:
        import time

        bundle = RuntimeBundle(now=time.time())
    panel_width = max(40, int(width) if width is not None else terminal_width())
    sections = bind_cockpit_fields(bundle)
    lines: list[str] = [
        _rule(panel_width, "="),
        fit_line("WINDOW 1 · TRADING COCKPIT", panel_width),
        fit_line("Trader view · short sources · Laboratory has full detail", panel_width),
        _rule(panel_width, "="),
    ]
    lines.extend(_section("1 · MARKET", sections["market"], panel_width=panel_width, now=bundle.now))
    lines.append(_rule(panel_width))
    lines.extend(
        _section("2 · AI DECISION", sections["ai_decision"], panel_width=panel_width, now=bundle.now)
    )
    lines.append(_rule(panel_width))
    lines.extend(
        _section("3 · NEXT TRIGGER", sections["next_trigger"], panel_width=panel_width, now=bundle.now)
    )
    lines.append(_rule(panel_width))
    lines.extend(_section("4 · ACCOUNT", sections["account"], panel_width=panel_width, now=bundle.now))
    lines.append(_rule(panel_width))
    lines.extend(
        _section(
            "5 · SYSTEM HEALTH",
            sections["system_health"],
            panel_width=panel_width,
            now=bundle.now,
        )
    )
    lines.append(_rule(panel_width))
    lines.extend(
        _section("6 · AI TIMELINE", sections["ai_timeline"], panel_width=panel_width, now=bundle.now)
    )
    lines.append(_rule(panel_width))
    lines.extend(
        _section(
            "7 · RECENT EVENTS",
            sections["recent_events"],
            panel_width=panel_width,
            now=bundle.now,
        )
    )
    lines.append(_rule(panel_width, "="))
    lines.append(
        fit_line("  Keys: 1 Cockpit  2 Laboratory  3 Developer  Q Quit  ? Help", panel_width)
    )
    lines = dedupe_consecutive(clamp_lines(lines, panel_width))
    return "\n".join(lines)
