"""Bind H-7.3 Professional Operator fields from published snapshots only.

Read-only. Never evaluates engines. Never imports engine packages.
"""

from __future__ import annotations

from hotirjam_ai5.mission_control.provenance import (
    NA,
    UNWIRED,
    ProvenancedField,
    bind,
    format_age,
    unbound,
)
from hotirjam_ai5.mission_control.runtime_bundle import RuntimeBundle


def _reasons(obj: object, *, limit: int = 3) -> str:
    reasons = getattr(obj, "reasons", None)
    if not reasons:
        return NA
    return " | ".join(str(r) for r in tuple(reasons)[:limit])


def _enum_val(value: object) -> str:
    if value is None:
        return NA
    return str(getattr(value, "value", value))


def bind_operator_regions(
    bundle: RuntimeBundle,
) -> dict[str, dict[str, ProvenancedField]]:
    """Return header / left / center / right / bottom provenanced maps."""
    now = bundle.now
    return {
        "header": _bind_header(bundle, now=now),
        "left": _bind_left(bundle, now=now),
        "center": _bind_center(bundle, now=now),
        "right": _bind_right(bundle, now=now),
        "bottom": _bind_bottom(bundle, now=now),
    }


def _bind_header(bundle: RuntimeBundle, *, now: float) -> dict[str, ProvenancedField]:
    dash = bundle.dashboard
    frame = bundle.frame
    ft = float(frame.timestamp) if frame is not None else None

    last_price: ProvenancedField
    if dash is not None:
        symbol = bind(
            dash.market.symbol,
            source_object="DashboardState.market",
            source_field="symbol",
            timestamp=None,
            now=now,
            digits=None,
        )
        last_price = bind(
            dash.market.last_price,
            source_object="DashboardState.market",
            source_field="last_price",
            timestamp=None,
            now=now,
        )
        market_state = bind(
            dash.market_state.state,
            source_object="DashboardState.market_state",
            source_field="state",
            timestamp=None,
            now=now,
            digits=None,
        )
        ai_status = bind(
            dash.trade_decision.decision,
            source_object="DashboardState.trade_decision",
            source_field="decision",
            timestamp=None,
            now=now,
            digits=None,
        )
        health = bind(
            dash.feed_health.feed_status.value,
            source_object="DashboardState.feed_health",
            source_field="feed_status",
            timestamp=None,
            now=now,
            digits=None,
        )
        session = bind(
            dash.system.market_status.value,
            source_object="DashboardState.system",
            source_field="market_status",
            timestamp=None,
            now=now,
            digits=None,
        )
    elif frame is not None:
        symbol = bind(
            frame.symbol,
            source_object="ValidatorFrame",
            source_field="symbol",
            timestamp=ft,
            now=now,
            digits=None,
        )
        last_price = bind(
            frame.current_price,
            source_object="ValidatorFrame",
            source_field="current_price",
            timestamp=ft,
            now=now,
        )
        market_state = unbound(
            reason=UNWIRED, source_object="ValidatorFrame", source_field="market_state"
        )
        ai_status = bind(
            frame.decision,
            source_object="ValidatorFrame",
            source_field="decision",
            timestamp=ft,
            now=now,
            digits=None,
        )
        health = ProvenancedField(
            value="BOUND",
            source_object="ValidatorFrame",
            source_field="present",
            timestamp=ft,
            display_age=format_age(now, ft),
        )
        session = unbound(
            reason=UNWIRED, source_object="ValidatorFrame", source_field="session"
        )
    else:
        symbol = unbound()
        last_price = unbound()
        market_state = unbound()
        ai_status = unbound()
        health = unbound()
        session = unbound()

    return {
        "Product": ProvenancedField(
            value="HOTIRJAM AI 5",
            source_object="runtime",
            source_field="product",
            timestamp=None,
            display_age=NA,
        ),
        "Session": session,
        "Symbol": symbol,
        "Last": last_price,
        "Market State": market_state,
        "AI Status": ai_status,
        "System Health": health,
        "Decision": ProvenancedField(
            value="DISABLED",
            source_object="runtime",
            source_field="decision_gate",
            timestamp=None,
            display_age=NA,
        ),
        "Execution": ProvenancedField(
            value="DISABLED",
            source_object="runtime",
            source_field="execution_gate",
            timestamp=None,
            display_age=NA,
        ),
    }


def _bind_left(bundle: RuntimeBundle, *, now: float) -> dict[str, ProvenancedField]:
    frame = bundle.frame
    dash = bundle.dashboard
    if frame is None:
        keys = (
            "Current Objective",
            "Current Initiative",
            "Response",
            "Continuation",
            "Break Capability",
            "Confidence",
            "Current Setup",
            "Risk State",
        )
        out = {k: unbound() for k in keys}
        if dash is not None:
            out["Confidence"] = bind(
                max(
                    dash.trade_decision.buy_confidence,
                    dash.trade_decision.sell_confidence,
                ),
                source_object="DashboardState.trade_decision",
                source_field="confidence",
                timestamp=None,
                now=now,
                digits=0,
            )
            out["Current Setup"] = bind(
                dash.trade_decision.decision,
                source_object="DashboardState.trade_decision",
                source_field="decision",
                timestamp=None,
                now=now,
                digits=None,
            )
            out["Risk State"] = bind(
                dash.account_status.risk_status,
                source_object="DashboardState.account_status",
                source_field="risk_status",
                timestamp=None,
                now=now,
                digits=None,
                empty=UNWIRED,
            )
        return out

    obj = frame.objective
    ini = frame.initiative
    rsp = frame.response
    cont = frame.continuation
    brk = frame.break_capability
    ft = float(frame.timestamp)

    objective_text = (
        NA
        if obj.nearest_high_price is None and obj.nearest_low_price is None
        else f"H={obj.nearest_high_price} L={obj.nearest_low_price}"
    )
    conf = max(
        float(getattr(ini, "confidence", 0.0) or 0.0),
        float(getattr(rsp, "confidence", 0.0) or 0.0),
        float(getattr(cont, "confidence", 0.0) or 0.0),
        float(getattr(brk, "confidence", 0.0) or 0.0),
    )
    setup = f"{_enum_val(ini.dominant_side)}/{_enum_val(rsp.response_state)}"
    risk = unbound(reason=NA, source_object="runtime", source_field="risk")
    if dash is not None:
        risk = bind(
            dash.account_status.risk_status,
            source_object="DashboardState.account_status",
            source_field="risk_status",
            timestamp=None,
            now=now,
            digits=None,
            empty=UNWIRED,
        )

    return {
        "Current Objective": ProvenancedField(
            value=objective_text,
            source_object="ValidatorFrame.objective",
            source_field="nearest_high_price|nearest_low_price",
            timestamp=obj.timestamp,
            display_age=format_age(now, obj.timestamp),
        ),
        "Current Initiative": ProvenancedField(
            value=(
                f"{_enum_val(ini.dominant_side)} "
                f"{_enum_val(ini.initiative_state)} "
                f"c={ini.confidence:.2f}"
            ),
            source_object="ValidatorFrame.initiative",
            source_field="dominant_side|initiative_state|confidence",
            timestamp=ini.timestamp,
            display_age=format_age(now, ini.timestamp),
        ),
        "Response": ProvenancedField(
            value=(
                f"{_enum_val(rsp.response_side)} "
                f"{_enum_val(rsp.response_state)} "
                f"s={rsp.response_strength:.2f}"
            ),
            source_object="ValidatorFrame.response",
            source_field="response_side|response_state|response_strength",
            timestamp=rsp.timestamp,
            display_age=format_age(now, rsp.timestamp),
        ),
        "Continuation": ProvenancedField(
            value=(
                f"{_enum_val(cont.continuation_side)} "
                f"{_enum_val(cont.state)} "
                f"sc={cont.continuation_score:.2f}"
            ),
            source_object="ValidatorFrame.continuation",
            source_field="continuation_side|state|continuation_score",
            timestamp=cont.timestamp,
            display_age=format_age(now, cont.timestamp),
        ),
        "Break Capability": ProvenancedField(
            value=(
                f"{_enum_val(brk.target_side)} "
                f"{_enum_val(brk.state)} "
                f"p={brk.break_probability:.2f}"
            ),
            source_object="ValidatorFrame.break_capability",
            source_field="target_side|state|break_probability",
            timestamp=brk.timestamp,
            display_age=format_age(now, brk.timestamp),
        ),
        "Confidence": ProvenancedField(
            value=f"{conf:.2f}",
            source_object="ValidatorFrame",
            source_field="confidence_max",
            timestamp=ft,
            display_age=format_age(now, ft),
        ),
        "Current Setup": ProvenancedField(
            value=setup,
            source_object="ValidatorFrame",
            source_field="initiative|response",
            timestamp=ft,
            display_age=format_age(now, ft),
        ),
        "Risk State": risk,
    }


def _bind_center(bundle: RuntimeBundle, *, now: float) -> dict[str, ProvenancedField]:
    frame = bundle.frame
    if frame is None:
        return {
            key: unbound()
            for key in (
                "Objective reasoning",
                "Initiative reasoning",
                "Response reasoning",
                "Module confidence",
                "Evidence",
                "Provenance",
                "Next trigger",
            )
        }

    obj = frame.objective
    ini = frame.initiative
    rsp = frame.response
    diag = getattr(frame, "objective_diagnostics", None)
    obj_reason = (
        f"high={_enum_val(obj.high_state)} low={_enum_val(obj.low_state)}"
        if diag is None
        else f"audit={type(diag).__name__}"
    )
    evidence = getattr(ini, "evidence", None)
    if evidence is not None:
        ev_text = (
            f"force={getattr(evidence, 'force', NA)} "
            f"energy={getattr(evidence, 'energy', NA)} "
            f"liq={getattr(evidence, 'liquidity', NA)}"
        )
    else:
        ev_text = NA

    return {
        "Objective reasoning": ProvenancedField(
            value=obj_reason,
            source_object="ValidatorFrame.objective",
            source_field="high_state|low_state|diagnostics",
            timestamp=obj.timestamp,
            display_age=format_age(now, obj.timestamp),
        ),
        "Initiative reasoning": ProvenancedField(
            value=_reasons(ini),
            source_object="ValidatorFrame.initiative",
            source_field="reasons",
            timestamp=ini.timestamp,
            display_age=format_age(now, ini.timestamp),
        ),
        "Response reasoning": ProvenancedField(
            value=_reasons(rsp),
            source_object="ValidatorFrame.response",
            source_field="reasons",
            timestamp=rsp.timestamp,
            display_age=format_age(now, rsp.timestamp),
        ),
        "Module confidence": ProvenancedField(
            value=(
                f"I={ini.confidence:.2f} R={rsp.confidence:.2f} "
                f"C={frame.continuation.confidence:.2f} "
                f"B={frame.break_capability.confidence:.2f}"
            ),
            source_object="ValidatorFrame",
            source_field="confidence",
            timestamp=float(frame.timestamp),
            display_age=format_age(now, float(frame.timestamp)),
        ),
        "Evidence": ProvenancedField(
            value=ev_text,
            source_object="ValidatorFrame.initiative.evidence",
            source_field="force|energy|liquidity",
            timestamp=ini.timestamp,
            display_age=format_age(now, ini.timestamp),
        ),
        "Provenance": ProvenancedField(
            value="ValidatorFrame (published)",
            source_object="ValidatorFrame",
            source_field="present",
            timestamp=float(frame.timestamp),
            display_age=format_age(now, float(frame.timestamp)),
        ),
        "Next trigger": unbound(
            reason=UNWIRED, source_object="runtime", source_field="trigger"
        ),
    }


def _bind_right(bundle: RuntimeBundle, *, now: float) -> dict[str, ProvenancedField]:
    dash = bundle.dashboard
    timing = bundle.loop_timing
    frame = bundle.frame

    if timing is not None:
        end = getattr(timing, "end_time", None)
        loop = bind(
            getattr(timing, "loop_ms"),
            source_object="LoopTimingSnapshot",
            source_field="loop_ms",
            timestamp=end,
            now=now,
            digits=2,
        )
        checkpoint = bind(
            getattr(timing, "checkpoint_ms"),
            source_object="LoopTimingSnapshot",
            source_field="checkpoint_ms",
            timestamp=end,
            now=now,
            digits=2,
        )
    else:
        loop = unbound(reason=UNWIRED, source_object="LoopTimingSnapshot", source_field="loop_ms")
        checkpoint = unbound(
            reason=UNWIRED, source_object="LoopTimingSnapshot", source_field="checkpoint_ms"
        )

    if dash is not None:
        feed = bind(
            dash.feed_health.feed_status.value,
            source_object="DashboardState.feed_health",
            source_field="feed_status",
            timestamp=None,
            now=now,
            digits=None,
        )
        runtime = bind(
            dash.system.engine_status.value,
            source_object="DashboardState.system",
            source_field="engine_status",
            timestamp=None,
            now=now,
            digits=None,
        )
        mem = dash.memory_panel
        memory = bind(
            f"{mem.consensus_direction}/{mem.consensus_status}",
            source_object="DashboardState.memory_panel",
            source_field="consensus",
            timestamp=None,
            now=now,
            digits=None,
        )
        events = (
            bind(
                str(dash.events[-1]),
                source_object="DashboardState",
                source_field="events",
                timestamp=None,
                now=now,
                digits=None,
            )
            if dash.events
            else unbound(reason=NA, source_object="DashboardState", source_field="events")
        )
    else:
        feed = (
            ProvenancedField(
                value="BOUND",
                source_object="ValidatorFrame",
                source_field="present",
                timestamp=float(frame.timestamp),
                display_age=format_age(now, float(frame.timestamp)),
            )
            if frame is not None
            else unbound()
        )
        runtime = unbound(reason=UNWIRED)
        memory = unbound(reason=UNWIRED)
        if bundle.transition_summaries:
            events = ProvenancedField(
                value=bundle.transition_summaries[-1],
                source_object="structural_transition_journal",
                source_field="summary",
                timestamp=float(frame.timestamp) if frame is not None else None,
                display_age=(
                    format_age(now, float(frame.timestamp)) if frame is not None else NA
                ),
            )
        else:
            events = unbound(reason=NA)

    warnings = unbound(reason=NA, source_object="runtime", source_field="warnings")
    if timing is not None:
        sev = getattr(timing, "logging_severity", None)
        if sev is not None:
            warnings = bind(
                _enum_val(sev),
                source_object="LoopTimingSnapshot",
                source_field="logging_severity",
                timestamp=getattr(timing, "end_time", None),
                now=now,
                digits=None,
            )

    return {
        "Loop time": loop,
        "Checkpoint": checkpoint,
        "Feed health": feed,
        "Runtime": runtime,
        "Memory": memory,
        "Events": events,
        "Warnings": warnings,
    }


def _bind_bottom(bundle: RuntimeBundle, *, now: float) -> dict[str, ProvenancedField]:
    del now
    frame = bundle.frame
    dash = bundle.dashboard
    messages = ProvenancedField(
        value="OBSERVE · Decision DISABLED · Execution DISABLED",
        source_object="runtime",
        source_field="operator_mode",
        timestamp=None,
        display_age=NA,
    )
    no_trade = unbound(reason=UNWIRED, source_object="runtime", source_field="no_trade")
    if dash is not None and dash.trade_decision.reason:
        no_trade = ProvenancedField(
            value=str(dash.trade_decision.reason),
            source_object="DashboardState.trade_decision",
            source_field="reason",
            timestamp=None,
            display_age=NA,
        )
    elif frame is not None and getattr(frame, "decision", None):
        no_trade = ProvenancedField(
            value=str(frame.decision),
            source_object="ValidatorFrame",
            source_field="decision",
            timestamp=float(frame.timestamp),
            display_age=NA,
        )

    cert = ProvenancedField(
        value="H-7.2D Display CERT · H-7.3 Operator UX",
        source_object="runtime",
        source_field="certification",
        timestamp=None,
        display_age=NA,
    )
    notices: list[str] = []
    if bundle.dashboard is None and bundle.frame is None:
        notices.append("No published runtime — UNWIRED")
    elif bundle.frame is None:
        notices.append("ValidatorFrame absent — Lab chain UNWIRED")
    elif bundle.dashboard is None:
        notices.append("DashboardState absent — account/feed partial")
    if not notices:
        notices.append("Runtime bound")

    return {
        "Operator Messages": messages,
        "No Trade reasons": no_trade,
        "Certification": cert,
        "System notices": ProvenancedField(
            value=" | ".join(notices),
            source_object="runtime",
            source_field="notices",
            timestamp=None,
            display_age=NA,
        ),
    }
