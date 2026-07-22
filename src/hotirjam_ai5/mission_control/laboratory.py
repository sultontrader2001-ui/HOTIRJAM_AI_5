"""Window 2 — AI Laboratory grouped module list (H-7.1). Presentation only."""

from __future__ import annotations

from hotirjam_ai5.mission_control.catalog import GROUP_ORDER, default_module_cards
from hotirjam_ai5.mission_control.models import ModuleCardState, ModuleGroup

_WIDTH = 78


def _rule(char: str = "-") -> str:
    return char * _WIDTH


def _collapsed_line(card: ModuleCardState, *, selected: bool) -> str:
    marker = ">" if selected else " "
    badge = card.spec.source_badge.value
    return (
        f"  {marker} [{card.spec.name}]  "
        f"Status={card.status}  Health={card.health}  "
        f"Latency={card.latency}  Last={card.last_update}  "
        f"Badge={badge}"
    )


def _expanded_block(card: ModuleCardState) -> list[str]:
    spec = card.spec
    deps = ", ".join(spec.dependencies) if spec.dependencies else "N/A"
    consumers = ", ".join(spec.consumers) if spec.consumers else "N/A"
    return [
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
        "    ------------------",
    ]


def render_laboratory(
    cards: list[ModuleCardState] | None = None,
    *,
    selected_index: int = 0,
) -> str:
    """Render grouped Laboratory list. Cards collapsed by default."""
    items = cards if cards is not None else default_module_cards()
    if not items:
        return "WINDOW 2 · AI LABORATORY\nN/A"
    index = max(0, min(selected_index, len(items) - 1))
    lines: list[str] = [
        "=" * _WIDTH,
        "WINDOW 2 · AI LABORATORY",
        "Read-only · Collapsed by default · Expand never evaluates",
        _rule("="),
    ]
    # Index map for selection marker
    flat_i = 0
    for group in GROUP_ORDER:
        group_cards = [c for c in items if c.spec.group is group]
        if not group_cards:
            continue
        lines.append(f"  [{group.value}]")
        for card in group_cards:
            selected = flat_i == index
            lines.append(_collapsed_line(card, selected=selected))
            if card.expanded:
                lines.extend(_expanded_block(card))
            flat_i += 1
        lines.append("")
    lines.append(_rule("="))
    lines.append(
        "  Keys: ↑/↓ or J/K select · Enter/E expand · 1/2/3 windows · Q Quit"
    )
    selected = items[index]
    lines.append(
        f"  Selected: {selected.spec.name}  "
        f"({'EXPANDED' if selected.expanded else 'collapsed'})  "
        f"Badge={selected.spec.source_badge.value}"
    )
    return "\n".join(lines)


def cards_in_group_order(cards: list[ModuleCardState]) -> list[ModuleCardState]:
    """Stable flat order matching Laboratory render order."""
    ordered: list[ModuleCardState] = []
    for group in GROUP_ORDER:
        ordered.extend(c for c in cards if c.spec.group is group)
    return ordered
