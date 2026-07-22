"""Static Laboratory module catalog (H-7.1). Presentation metadata only."""

from __future__ import annotations

from hotirjam_ai5.mission_control.models import (
    ModuleCardState,
    ModuleGroup,
    ModuleSpec,
    SourceBadge,
)

MODULE_CATALOG: tuple[ModuleSpec, ...] = (
    # DATA
    ModuleSpec(
        module_id="data",
        name="Data",
        group=ModuleGroup.DATA,
        source_badge=SourceBadge.LIVE,
        purpose="Ingest live market observations (ticks / optional DOM).",
        dependencies=(),
        consumers=("Normalizer", "Physics", "Liquidity"),
    ),
    ModuleSpec(
        module_id="normalizer",
        name="Normalizer",
        group=ModuleGroup.DATA,
        source_badge=SourceBadge.LIVE,
        purpose="Build engine-ready structure (bars, confirmed swings).",
        dependencies=("Data",),
        consumers=("Objective", "Initiative evidence", "Response"),
    ),
    # MARKET
    ModuleSpec(
        module_id="physics",
        name="Physics",
        group=ModuleGroup.MARKET,
        source_badge=SourceBadge.DASH,
        purpose="Describe price motion (spread, mid, velocity, acceleration).",
        dependencies=("Data",),
        consumers=("Market State",),
    ),
    ModuleSpec(
        module_id="force",
        name="Force",
        group=ModuleGroup.MARKET,
        source_badge=SourceBadge.INI,
        purpose="Directional push / impulse (Initiative evidence field).",
        dependencies=("Normalizer",),
        consumers=("Objective chain",),
    ),
    ModuleSpec(
        module_id="energy",
        name="Energy",
        group=ModuleGroup.MARKET,
        source_badge=SourceBadge.INI,
        purpose="Local auction activity / range-volume energy (Initiative evidence).",
        dependencies=("Normalizer",),
        consumers=("Objective chain",),
    ),
    ModuleSpec(
        module_id="liquidity",
        name="Liquidity",
        group=ModuleGroup.MARKET,
        source_badge=SourceBadge.MIX,
        purpose="Liquidity imbalance / shift (DOM dashboard and/or Initiative).",
        dependencies=("Data", "Normalizer"),
        consumers=("Market State", "Objective chain"),
    ),
    # INTELLIGENCE
    ModuleSpec(
        module_id="market_state",
        name="Market State",
        group=ModuleGroup.INTELLIGENCE,
        source_badge=SourceBadge.DASH,
        purpose="Classify market regime and direction.",
        dependencies=("Physics", "Liquidity"),
        consumers=("Memory", "Decision spine"),
    ),
    ModuleSpec(
        module_id="memory",
        name="Memory",
        group=ModuleGroup.INTELLIGENCE,
        source_badge=SourceBadge.DASH,
        purpose="Short-horizon market / decision memory for audit and influence.",
        dependencies=("Market State",),
        consumers=("Decision spine",),
    ),
    ModuleSpec(
        module_id="objective",
        name="Objective",
        group=ModuleGroup.INTELLIGENCE,
        source_badge=SourceBadge.LIVE,
        purpose="Nearest eligible structural High / Low battlefield.",
        dependencies=("Normalizer", "Hierarchy"),
        consumers=("Response", "Continuation", "Break", "Logger"),
    ),
    ModuleSpec(
        module_id="response",
        name="Response",
        group=ModuleGroup.INTELLIGENCE,
        source_badge=SourceBadge.LIVE,
        purpose="How price reacts to Objectives under Initiative.",
        dependencies=("Objective", "Initiative"),
        consumers=("Continuation", "Break"),
    ),
    ModuleSpec(
        module_id="continuation",
        name="Continuation",
        group=ModuleGroup.INTELLIGENCE,
        source_badge=SourceBadge.LIVE,
        purpose="Whether the response is continuing or decaying.",
        dependencies=("Objective", "Response"),
        consumers=("Break",),
    ),
    ModuleSpec(
        module_id="break",
        name="Break",
        group=ModuleGroup.INTELLIGENCE,
        source_badge=SourceBadge.LIVE,
        purpose="Break capability against structural objectives.",
        dependencies=("Objective", "Response", "Continuation"),
        consumers=("Risk",),
    ),
    # EXECUTION
    ModuleSpec(
        module_id="risk",
        name="Risk",
        group=ModuleGroup.EXECUTION,
        source_badge=SourceBadge.NA,
        purpose="Constrain size / exposure before execution (not implemented).",
        dependencies=("Break", "Account"),
        consumers=("Execution",),
    ),
    ModuleSpec(
        module_id="execution",
        name="Execution",
        group=ModuleGroup.EXECUTION,
        source_badge=SourceBadge.OFF,
        purpose="Broker order path — intentionally DISABLED.",
        dependencies=("Risk",),
        consumers=(),
    ),
    # SYSTEM
    ModuleSpec(
        module_id="logger",
        name="Logger",
        group=ModuleGroup.SYSTEM,
        source_badge=SourceBadge.LIVE,
        purpose="Persist observation frames (diagnostic projection P only).",
        dependencies=("ValidatorFrame",),
        consumers=("Replay", "Certification"),
    ),
    ModuleSpec(
        module_id="checkpoint",
        name="Checkpoint",
        group=ModuleGroup.SYSTEM,
        source_badge=SourceBadge.LIVE,
        purpose="Persist hierarchy / initiative state across restarts.",
        dependencies=("Hierarchy", "Initiative"),
        consumers=("Restore", "Certification"),
    ),
)

GROUP_ORDER: tuple[ModuleGroup, ...] = (
    ModuleGroup.DATA,
    ModuleGroup.MARKET,
    ModuleGroup.INTELLIGENCE,
    ModuleGroup.EXECUTION,
    ModuleGroup.SYSTEM,
)


def default_module_cards() -> list[ModuleCardState]:
    """Collapsed cards with honest UNWIRED / N/A placeholders."""
    cards: list[ModuleCardState] = []
    for spec in MODULE_CATALOG:
        status = "DISABLED" if spec.source_badge is SourceBadge.OFF else "UNWIRED"
        if spec.source_badge is SourceBadge.NA:
            status = "N/A"
        cards.append(
            ModuleCardState(
                spec=spec,
                expanded=False,
                status=status,
                health="N/A",
                latency="N/A",
                last_update="N/A",
                identity=spec.name,
                inputs="N/A",
                processing="UNWIRED",
                outputs="N/A",
                confidence="N/A",
                reason="H-7.1 shell — no runtime binding",
                history="N/A",
                performance="N/A",
            )
        )
    return cards
