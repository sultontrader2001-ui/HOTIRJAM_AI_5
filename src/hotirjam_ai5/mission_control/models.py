"""Mission Control UI models — presentation state only (H-7.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class MissionWindow(StrEnum):
    """Top-level Mission Control windows."""

    OPERATOR = "OPERATOR"
    COCKPIT = "COCKPIT"
    LABORATORY = "LABORATORY"
    DEVELOPER = "DEVELOPER"


class SourceBadge(StrEnum):
    """Honesty badge for module wiring (H-7.0 / H-7.1)."""

    LIVE = "LIVE"
    DASH = "DASH"
    INI = "INI"
    OFF = "OFF"
    NA = "N/A"
    MIX = "MIX"


class ModuleGroup(StrEnum):
    """Laboratory module groups."""

    DATA = "DATA"
    MARKET = "MARKET"
    INTELLIGENCE = "INTELLIGENCE"
    EXECUTION = "EXECUTION"
    SYSTEM = "SYSTEM"


NA = "N/A"
UNWIRED = "UNWIRED"


@dataclass(frozen=True, slots=True)
class ModuleSpec:
    """Static module identity for the Laboratory catalog."""

    module_id: str
    name: str
    group: ModuleGroup
    source_badge: SourceBadge
    purpose: str
    dependencies: tuple[str, ...] = ()
    consumers: tuple[str, ...] = ()


@dataclass(slots=True)
class ModuleCardState:
    """Collapsed/expanded presentation state for one module card."""

    spec: ModuleSpec
    expanded: bool = False
    status: str = UNWIRED
    health: str = NA
    latency: str = NA
    last_update: str = NA
    # Expanded placeholders — never fabricated numeric truth.
    identity: str = NA
    inputs: str = NA
    processing: str = NA
    outputs: str = NA
    confidence: str = NA
    reason: str = NA
    history: str = NA
    performance: str = NA


@dataclass(slots=True)
class CockpitPanelState:
    """Cockpit field bag — placeholders until later wiring sprints."""

    market: dict[str, str] = field(default_factory=dict)
    ai_decision: dict[str, str] = field(default_factory=dict)
    next_trigger: dict[str, str] = field(default_factory=dict)
    account: dict[str, str] = field(default_factory=dict)
    system_health: dict[str, str] = field(default_factory=dict)
    ai_timeline: dict[str, str] = field(default_factory=dict)
    recent_events: tuple[str, ...] = ()


def default_cockpit_placeholders() -> CockpitPanelState:
    """Honest empty cockpit — N/A / UNWIRED only, no simulated values."""
    na = NA
    return CockpitPanelState(
        market={
            "Symbol": na,
            "Last": na,
            "Bid/Ask": na,
            "Spread": na,
            "Tick Rate": na,
            "Latency": na,
            "Session": na,
        },
        ai_decision={
            "Side": na,
            "Action": na,
            "Confidence": na,
            "Grade": na,
            "Reason": na,
            "Architecture": UNWIRED,
            "Decision Engine": "DISABLED",
            "Execution": "DISABLED",
        },
        next_trigger={
            "Condition": UNWIRED,
            "Distance": na,
            "Note": "Presentation shell only — no predicates yet",
        },
        account={
            "Equity": na,
            "Open P&L": na,
            "Day P&L": na,
            "Positions": na,
            "Risk Status": UNWIRED,
        },
        system_health={
            "Feed": UNWIRED,
            "Engines": UNWIRED,
            "Logger": UNWIRED,
            "Checkpoint": UNWIRED,
            "Loop ms": na,
            "Checkpoint ms": na,
            "Logger ms": na,
            "Stale": na,
        },
        ai_timeline={
            "Last Event": UNWIRED,
            "Sequence": na,
            "Note": "Timeline wiring deferred",
        },
        recent_events=("N/A — no events bound in H-7.1 shell",),
    )
