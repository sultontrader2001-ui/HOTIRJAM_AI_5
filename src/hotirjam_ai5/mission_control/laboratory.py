"""Window 2 — AI Laboratory (H-7.2A.1 width-safe rendering)."""

from __future__ import annotations

from hotirjam_ai5.mission_control.bind_laboratory import bind_laboratory_cards
from hotirjam_ai5.mission_control.catalog import GROUP_ORDER, default_module_cards
from hotirjam_ai5.mission_control.models import ModuleCardState
from hotirjam_ai5.mission_control.render_format import (
    clamp_lines,
    dedupe_consecutive,
    fit_line,
    terminal_width,
    truncate,
)
from hotirjam_ai5.mission_control.runtime_bundle import RuntimeBundle


def _rule(width: int, char: str = "-") -> str:
    return char * width


def _collapsed_line(card: ModuleCardState, *, selected: bool, width: int) -> str:
    marker = ">" if selected else " "
    badge = card.spec.source_badge.value
    raw = (
        f"  {marker} [{card.spec.name}]  "
        f"Status={card.status}  Health={card.health}  "
        f"Latency={card.latency}  Last={card.last_update}  "
        f"Badge={badge}"
    )
    return fit_line(raw, width)


def _expanded_block(card: ModuleCardState, *, width: int) -> list[str]:
    spec = card.spec
    deps = ", ".join(spec.dependencies) if spec.dependencies else "N/A"
    consumers = ", ".join(spec.consumers) if spec.consumers else "N/A"
    rows = [
        "    ---- EXPANDED ----",
        f"    Identity ...... {card.identity}",
        f"    Purpose ....... {spec.purpose}",
        f"    Inputs ........ {card.inputs}",
        f"    Processing .... {card.processing}",
        f"    Outputs ....... {card.outputs}",
        f"    Dependencies .. {deps}",
        f"    Consumers ..... {consumers}",
        f"    Confidence .... {card.confidence}",
        f"    Reason ........ {card.reason}",
        f"    History ....... {card.history}",
        f"    Performance ... {card.performance}",
        f"    Source Badge .. {spec.source_badge.value}",
        "    ------------------",
    ]
    return [fit_line(truncate(r, width), width) for r in rows]


def render_laboratory(
    cards: list[ModuleCardState] | None = None,
    *,
    selected_index: int = 0,
    bundle: RuntimeBundle | None = None,
    width: int | None = None,
) -> str:
    """Render grouped Laboratory list bound from runtime when provided."""
    panel_width = max(40, int(width) if width is not None else terminal_width())
    items = cards if cards is not None else default_module_cards()
    items = cards_in_group_order(items)
    if bundle is not None:
        bind_laboratory_cards(items, bundle)
    if not items:
        return fit_line("WINDOW 2 · AI LABORATORY", panel_width) + "\nN/A"
    index = max(0, min(selected_index, len(items) - 1))
    lines: list[str] = [
        _rule(panel_width, "="),
        "WINDOW 2 · AI LABORATORY",
        "Full module detail · paths truncated to terminal width",
        _rule(panel_width, "="),
    ]
    flat_i = 0
    for group in GROUP_ORDER:
        group_cards = [c for c in items if c.spec.group is group]
        if not group_cards:
            continue
        lines.append(f"  [{group.value}]")
        for card in group_cards:
            selected = flat_i == index
            lines.append(
                _collapsed_line(card, selected=selected, width=panel_width)
            )
            if card.expanded:
                lines.extend(_expanded_block(card, width=panel_width))
            flat_i += 1
        lines.append("")
    lines.append(_rule(panel_width, "="))
    lines.append(
        "  Keys: ↑/↓ or J/K select · Enter/E expand · 1/2/3 windows · Q Quit"
    )
    selected = items[index]
    lines.append(
        f"  Selected: {selected.spec.name}  "
        f"({'EXPANDED' if selected.expanded else 'collapsed'})  "
        f"Badge={selected.spec.source_badge.value}"
    )
    lines = dedupe_consecutive(clamp_lines(lines, panel_width))
    return "\n".join(lines)


def cards_in_group_order(cards: list[ModuleCardState]) -> list[ModuleCardState]:
    """Stable flat order matching Laboratory render order."""
    ordered: list[ModuleCardState] = []
    for group in GROUP_ORDER:
        ordered.extend(c for c in cards if c.spec.group is group)
    return ordered
