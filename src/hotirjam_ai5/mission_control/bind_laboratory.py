"""Bind Window 2 Laboratory module cards from existing runtime (H-7.2)."""

from __future__ import annotations

from hotirjam_ai5.mission_control.models import ModuleCardState, SourceBadge
from hotirjam_ai5.mission_control.provenance import NA, UNWIRED, format_age, fmt_value
from hotirjam_ai5.mission_control.runtime_bundle import RuntimeBundle


def _join_reasons(reasons: tuple[str, ...] | None) -> str:
    if not reasons:
        return NA
    return " | ".join(reasons[:4])


def bind_laboratory_cards(
    cards: list[ModuleCardState],
    bundle: RuntimeBundle,
) -> list[ModuleCardState]:
    """Update card fields from runtime. Preserves expanded/selection state."""
    now = bundle.now
    dash = bundle.dashboard
    frame = bundle.frame
    timing = bundle.loop_timing
    ft = float(frame.timestamp) if frame is not None else None
    age = format_age(now, ft)

    by_id = {c.spec.module_id: c for c in cards}

    def _set(
        module_id: str,
        *,
        status: str,
        health: str = NA,
        latency: str = NA,
        last_update: str = NA,
        inputs: str = NA,
        outputs: str = NA,
        confidence: str = NA,
        reason: str = NA,
        history: str = NA,
        performance: str = NA,
        processing: str = NA,
    ) -> None:
        card = by_id.get(module_id)
        if card is None:
            return
        card.status = status
        card.health = health
        card.latency = latency
        card.last_update = last_update
        card.inputs = inputs
        card.outputs = outputs
        card.confidence = confidence
        card.reason = reason
        card.history = history
        card.performance = performance
        card.processing = processing
        card.identity = card.spec.name

    # DATA
    if frame is not None:
        _set(
            "data",
            status="BOUND",
            health=NA,
            latency=NA,
            last_update=age,
            inputs="LiveTick path (pre-evaluated frame)",
            outputs=f"symbol={frame.symbol} price={fmt_value(frame.current_price)}",
            reason="ValidatorFrame present",
            history=NA,
            performance=NA,
            processing="UNWIRED",
        )
        _set(
            "normalizer",
            status="BOUND",
            last_update=age,
            inputs="candles/swings on frame",
            outputs=(
                f"candles={frame.candle_count} "
                f"highs={frame.swing_high_count} lows={frame.swing_low_count}"
            ),
            reason="Counts from ValidatorFrame",
            processing="UNWIRED",
        )
    elif dash is not None and dash.market.last_price is not None:
        _set(
            "data",
            status="BOUND",
            last_update=NA,
            outputs=(
                f"symbol={dash.market.symbol} "
                f"last={fmt_value(dash.market.last_price)}"
            ),
            reason="DashboardState.market",
            health=dash.feed_health.feed_status.value,
        )
        _set("normalizer", status=UNWIRED, reason="No ValidatorFrame")
    else:
        _set("data", status=UNWIRED)
        _set("normalizer", status=UNWIRED)

    # MARKET — Physics (DASH)
    if dash is not None:
        p = dash.physics
        _set(
            "physics",
            status="BOUND",
            health=NA,
            last_update=NA,
            inputs="DashboardState.physics",
            outputs=(
                f"spread={fmt_value(p.spread)} mid={fmt_value(p.mid_price)} "
                f"vel={fmt_value(p.tick_velocity)} acc={fmt_value(p.tick_acceleration)}"
            ),
            reason="Dashboard physics view",
            processing="UNWIRED",
        )
        liq = dash.liquidity
        _set(
            "liquidity",
            status="BOUND",
            inputs="DashboardState.liquidity (+ optional Initiative)",
            outputs=f"shift={liq.shift} imbalance={liq.imbalance}",
            reason="Dashboard LiquidityView",
        )
    else:
        _set("physics", status=UNWIRED, reason="No DashboardState")
        _set("liquidity", status=UNWIRED, reason="No DashboardState")

    # Force / Energy from Initiative evidence on frame
    if frame is not None:
        ev = frame.initiative.evidence
        _set(
            "force",
            status="BOUND",
            last_update=format_age(now, frame.initiative.timestamp),
            inputs="ValidatorFrame.initiative.evidence",
            outputs=f"force={fmt_value(ev.force)}",
            confidence=fmt_value(frame.initiative.confidence),
            reason=_join_reasons(frame.initiative.reasons),
            processing="INI evidence field",
        )
        _set(
            "energy",
            status="BOUND",
            last_update=format_age(now, frame.initiative.timestamp),
            inputs="ValidatorFrame.initiative.evidence",
            outputs=f"energy={fmt_value(ev.energy)}",
            confidence=fmt_value(frame.initiative.confidence),
            reason=_join_reasons(frame.initiative.reasons),
            processing="INI evidence field",
        )
        # MIX liquidity: overlay initiative liquidity if dash missing
        if dash is None:
            _set(
                "liquidity",
                status="BOUND",
                inputs="ValidatorFrame.initiative.evidence.liquidity",
                outputs=f"liquidity={fmt_value(ev.liquidity)}",
                reason="Initiative evidence only",
                processing="INI",
            )
    else:
        _set("force", status=UNWIRED, reason="No Initiative on frame")
        _set("energy", status=UNWIRED, reason="No Initiative on frame")

    # INTELLIGENCE — Market State / Memory (DASH)
    if dash is not None:
        ms = dash.market_state
        _set(
            "market_state",
            status="BOUND",
            inputs="DashboardState.market_state",
            outputs=f"state={ms.state}",
            reason=ms.reason or NA,
        )
        mem = dash.memory_panel
        _set(
            "memory",
            status="BOUND",
            inputs="DashboardState.memory_panel",
            outputs=(
                f"consensus={mem.consensus_direction} "
                f"status={mem.consensus_status}"
            ),
            confidence=fmt_value(mem.consensus_confidence),
            reason="MemoryPanelView",
        )
    else:
        _set("market_state", status=UNWIRED)
        _set("memory", status=UNWIRED)

    # Objective / Response / Continuation / Break (LIVE frame)
    if frame is not None:
        obj = frame.objective
        _set(
            "objective",
            status="BOUND",
            last_update=format_age(now, obj.timestamp),
            inputs=(
                f"price={fmt_value(obj.current_price)} "
                f"candles={frame.candle_count}"
            ),
            outputs=(
                f"high={fmt_value(obj.nearest_high_price)} "
                f"low={fmt_value(obj.nearest_low_price)}"
            ),
            confidence=NA,
            reason=(
                f"high_state={fmt_value(obj.high_state)} "
                f"low_state={fmt_value(obj.low_state)}"
            ),
            history=(
                NA
                if not bundle.transition_summaries
                else " | ".join(bundle.transition_summaries[-3:])
            ),
            processing="Existing ObjectiveSnapshot on frame",
        )
        rsp = frame.response
        _set(
            "response",
            status="BOUND",
            last_update=format_age(now, rsp.timestamp),
            inputs="Objective+Initiative on frame",
            outputs=(
                f"side={rsp.response_side.value} "
                f"state={rsp.response_state.value} "
                f"strength={fmt_value(rsp.response_strength)}"
            ),
            confidence=fmt_value(rsp.confidence),
            reason=_join_reasons(rsp.reasons),
        )
        cont = frame.continuation
        _set(
            "continuation",
            status="BOUND",
            last_update=format_age(now, cont.timestamp),
            inputs="Response chain on frame",
            outputs=(
                f"side={cont.continuation_side.value} "
                f"score={fmt_value(cont.continuation_score)} "
                f"state={cont.state.value}"
            ),
            confidence=fmt_value(cont.confidence),
            reason=_join_reasons(cont.reasons),
        )
        brk = frame.break_capability
        _set(
            "break",
            status="BOUND",
            last_update=format_age(now, brk.timestamp),
            inputs="Full architecture chain on frame",
            outputs=(
                f"target={brk.target_side.value} "
                f"prob={fmt_value(brk.break_probability)} "
                f"state={brk.state.value}"
            ),
            confidence=fmt_value(brk.confidence),
            reason=_join_reasons(brk.reasons),
        )
    else:
        for mid in ("objective", "response", "continuation", "break"):
            _set(mid, status=UNWIRED, reason="No ValidatorFrame")

    # EXECUTION
    _set(
        "risk",
        status=NA,
        health=NA,
        reason="Risk engine not present",
        processing=UNWIRED,
    )
    _set(
        "execution",
        status="DISABLED",
        health=NA,
        reason="Execution path DISABLED",
        outputs="DISABLED",
        processing="OFF",
    )

    # SYSTEM — Logger / Checkpoint from loop timing only
    if timing is not None:
        _set(
            "logger",
            status="BOUND",
            health=timing.logging_severity.value,
            latency=f"{timing.logging_ms:.2f}ms",
            last_update=format_age(now, timing.end_time),
            inputs="ValidatorFrame (already logged upstream)",
            outputs=f"logging_ms={timing.logging_ms:.2f}",
            reason="LoopTimingSnapshot.logging_*",
            performance=f"severity={timing.logging_severity.value}",
            processing="UNWIRED",
        )
        _set(
            "checkpoint",
            status="BOUND",
            health=timing.checkpoint_severity.value,
            latency=f"{timing.checkpoint_ms:.2f}ms",
            last_update=format_age(now, timing.end_time),
            inputs="Hierarchy/Initiative checkpoint path",
            outputs=f"checkpoint_ms={timing.checkpoint_ms:.2f}",
            reason="LoopTimingSnapshot.checkpoint_*",
            performance=f"severity={timing.checkpoint_severity.value}",
        )
    else:
        _set("logger", status=UNWIRED, reason="No LoopTimingSnapshot")
        _set("checkpoint", status=UNWIRED, reason="No LoopTimingSnapshot")

    # Preserve catalog badges (static honesty)
    for card in cards:
        if card.spec.source_badge is SourceBadge.OFF:
            card.status = "DISABLED"
        if card.spec.source_badge is SourceBadge.NA and card.spec.module_id == "risk":
            card.status = NA

    return cards
