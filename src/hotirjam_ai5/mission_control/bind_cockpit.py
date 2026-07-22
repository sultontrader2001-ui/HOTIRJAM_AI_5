"""Bind Window 1 Cockpit fields from existing runtime objects (H-7.2)."""

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


def bind_cockpit_fields(bundle: RuntimeBundle) -> dict[str, dict[str, ProvenancedField]]:
    """Return provenanced cockpit sections. Never fabricates values."""
    now = bundle.now
    timing = bundle.loop_timing
    ft = float(bundle.frame.timestamp) if bundle.frame is not None else None
    return {
        "market": _bind_market(bundle, now=now, ft=ft),
        "ai_decision": _bind_decision(bundle, now=now, ft=ft),
        "next_trigger": {
            "Condition": unbound(
                reason=UNWIRED, source_object="runtime", source_field="trigger"
            ),
            "Distance": unbound(
                reason=UNWIRED, source_object="runtime", source_field="trigger"
            ),
            "Note": ProvenancedField(
                value="No trigger object in runtime",
                source_object="runtime",
                source_field="trigger",
                timestamp=None,
                display_age=NA,
            ),
        },
        "account": _bind_account(bundle, now=now),
        "system_health": _bind_system(bundle, now=now, timing=timing),
        "ai_timeline": _bind_timeline(bundle),
        "recent_events": _bind_events(bundle, ft=ft),
    }


def _bind_market(
    bundle: RuntimeBundle, *, now: float, ft: float | None
) -> dict[str, ProvenancedField]:
    dash = bundle.dashboard
    frame = bundle.frame
    if dash is not None:
        m = dash.market
        return {
            "Symbol": bind(
                m.symbol,
                source_object="DashboardState.market",
                source_field="symbol",
                timestamp=None,
                now=now,
                digits=None,
            ),
            "Last Price": bind(
                m.last_price,
                source_object="DashboardState.market",
                source_field="last_price",
                timestamp=None,
                now=now,
            ),
            "Bid": bind(
                m.bid,
                source_object="DashboardState.market",
                source_field="bid",
                timestamp=None,
                now=now,
            ),
            "Ask": bind(
                m.ask,
                source_object="DashboardState.market",
                source_field="ask",
                timestamp=None,
                now=now,
            ),
            "Spread": bind(
                m.spread,
                source_object="DashboardState.market",
                source_field="spread",
                timestamp=None,
                now=now,
            ),
            "Tick Rate": bind(
                dash.statistics.tick_rate,
                source_object="DashboardState.statistics",
                source_field="tick_rate",
                timestamp=None,
                now=now,
            ),
            "Session": bind(
                dash.system.market_status.value,
                source_object="DashboardState.system",
                source_field="market_status",
                timestamp=None,
                now=now,
                digits=None,
            ),
        }
    if frame is not None:
        return {
            "Symbol": bind(
                frame.symbol,
                source_object="ValidatorFrame",
                source_field="symbol",
                timestamp=ft,
                now=now,
                digits=None,
            ),
            "Last Price": bind(
                frame.current_price,
                source_object="ValidatorFrame",
                source_field="current_price",
                timestamp=ft,
                now=now,
            ),
            "Bid": unbound(
                reason=UNWIRED, source_object="ValidatorFrame", source_field="bid"
            ),
            "Ask": unbound(
                reason=UNWIRED, source_object="ValidatorFrame", source_field="ask"
            ),
            "Spread": unbound(
                reason=UNWIRED, source_object="ValidatorFrame", source_field="spread"
            ),
            "Tick Rate": unbound(
                reason=UNWIRED,
                source_object="ValidatorFrame",
                source_field="tick_rate",
            ),
            "Session": unbound(
                reason=UNWIRED, source_object="ValidatorFrame", source_field="session"
            ),
        }
    return {
        key: unbound()
        for key in (
            "Symbol",
            "Last Price",
            "Bid",
            "Ask",
            "Spread",
            "Tick Rate",
            "Session",
        )
    }


def _bind_decision(
    bundle: RuntimeBundle, *, now: float, ft: float | None
) -> dict[str, ProvenancedField]:
    dash = bundle.dashboard
    frame = bundle.frame
    fields: dict[str, ProvenancedField] = {}

    if dash is not None:
        td = dash.trade_decision
        fields["Direction"] = bind(
            td.decision,
            source_object="DashboardState.trade_decision",
            source_field="decision",
            timestamp=None,
            now=now,
            digits=None,
        )
        fields["Action"] = bind(
            td.next_action,
            source_object="DashboardState.trade_decision",
            source_field="next_action",
            timestamp=None,
            now=now,
            digits=None,
        )
        if td.decision == "BUY_INTERNAL":
            conf, conf_field = td.buy_confidence, "buy_confidence"
        elif td.decision == "SELL_INTERNAL":
            conf, conf_field = td.sell_confidence, "sell_confidence"
        else:
            conf = max(td.buy_confidence, td.sell_confidence)
            conf_field = "buy_confidence|sell_confidence"
        fields["Confidence"] = bind(
            conf,
            source_object="DashboardState.trade_decision",
            source_field=conf_field,
            timestamp=None,
            now=now,
            digits=0,
        )
        fields["Reason"] = bind(
            td.reason or NA,
            source_object="DashboardState.trade_decision",
            source_field="reason",
            timestamp=None,
            now=now,
            digits=None,
        )
    elif frame is not None:
        fields["Direction"] = bind(
            frame.decision,
            source_object="ValidatorFrame",
            source_field="decision",
            timestamp=ft,
            now=now,
            digits=None,
        )
        fields["Action"] = unbound(reason=UNWIRED)
        fields["Confidence"] = unbound(reason=UNWIRED)
        fields["Reason"] = unbound(reason=UNWIRED)
    else:
        fields["Direction"] = unbound()
        fields["Action"] = unbound()
        fields["Confidence"] = unbound()
        fields["Reason"] = unbound()

    fields["Grade"] = unbound(reason=NA, source_object="runtime", source_field="grade")

    if frame is not None:
        obj = frame.objective
        high = obj.nearest_high_price
        low = obj.nearest_low_price
        text = NA if high is None and low is None else f"H={high} L={low}"
        fields["Objective"] = ProvenancedField(
            value=text,
            source_object="ValidatorFrame.objective",
            source_field="nearest_high_price|nearest_low_price",
            timestamp=obj.timestamp,
            display_age=format_age(now, obj.timestamp),
        )
    else:
        fields["Objective"] = unbound(
            reason=UNWIRED,
            source_object="ValidatorFrame.objective",
            source_field="nearest_high_price|nearest_low_price",
        )
    return fields


def _bind_account(bundle: RuntimeBundle, *, now: float) -> dict[str, ProvenancedField]:
    dash = bundle.dashboard
    if dash is None:
        return {
            key: unbound()
            for key in ("Equity", "Open P&L", "Day P&L", "Positions", "Risk Status")
        }
    a = dash.account_status
    return {
        "Equity": bind(
            a.current_equity,
            source_object="DashboardState.account_status",
            source_field="current_equity",
            timestamp=None,
            now=now,
        ),
        "Open P&L": bind(
            dash.position_status.current_pnl,
            source_object="DashboardState.position_status",
            source_field="current_pnl",
            timestamp=None,
            now=now,
        ),
        "Day P&L": bind(
            a.today_pnl,
            source_object="DashboardState.account_status",
            source_field="today_pnl",
            timestamp=None,
            now=now,
        ),
        "Positions": bind(
            dash.position_status.status,
            source_object="DashboardState.position_status",
            source_field="status",
            timestamp=None,
            now=now,
            digits=None,
        ),
        "Risk Status": bind(
            a.risk_status,
            source_object="DashboardState.account_status",
            source_field="risk_status",
            timestamp=None,
            now=now,
            digits=None,
            empty=UNWIRED,
        ),
    }


def _bind_system(
    bundle: RuntimeBundle,
    *,
    now: float,
    timing: object | None,
) -> dict[str, ProvenancedField]:
    dash = bundle.dashboard
    if dash is not None:
        return {
            "Feed": bind(
                dash.feed_health.feed_status.value,
                source_object="DashboardState.feed_health",
                source_field="feed_status",
                timestamp=None,
                now=now,
                digits=None,
            ),
            "Engines": bind(
                dash.system.engine_status.value,
                source_object="DashboardState.system",
                source_field="engine_status",
                timestamp=None,
                now=now,
                digits=None,
            ),
            "Logger": unbound(
                reason=UNWIRED, source_object="DashboardState", source_field="logger"
            ),
            "Checkpoint": unbound(
                reason=UNWIRED,
                source_object="DashboardState",
                source_field="checkpoint",
            ),
            "Loop ms": unbound(reason=UNWIRED),
            "Checkpoint ms": unbound(reason=UNWIRED),
            "Logger ms": unbound(reason=UNWIRED),
            "Stale": bind(
                dash.feed_health.feed_status.value,
                source_object="DashboardState.feed_health",
                source_field="feed_status",
                timestamp=None,
                now=now,
                digits=None,
            ),
        }

    if timing is not None:
        end = getattr(timing, "end_time", None)
        return {
            "Feed": unbound(reason=UNWIRED),
            "Engines": unbound(reason=UNWIRED),
            "Logger": bind(
                getattr(timing, "logging_severity").value,
                source_object="LoopTimingSnapshot",
                source_field="logging_severity",
                timestamp=end,
                now=now,
                digits=None,
            ),
            "Checkpoint": bind(
                getattr(timing, "checkpoint_severity").value,
                source_object="LoopTimingSnapshot",
                source_field="checkpoint_severity",
                timestamp=end,
                now=now,
                digits=None,
            ),
            "Loop ms": bind(
                getattr(timing, "loop_ms"),
                source_object="LoopTimingSnapshot",
                source_field="loop_ms",
                timestamp=end,
                now=now,
                digits=2,
            ),
            "Checkpoint ms": bind(
                getattr(timing, "checkpoint_ms"),
                source_object="LoopTimingSnapshot",
                source_field="checkpoint_ms",
                timestamp=end,
                now=now,
                digits=2,
            ),
            "Logger ms": bind(
                getattr(timing, "logging_ms"),
                source_object="LoopTimingSnapshot",
                source_field="logging_ms",
                timestamp=end,
                now=now,
                digits=2,
            ),
            "Stale": unbound(reason=UNWIRED),
        }

    return {
        key: unbound()
        for key in (
            "Feed",
            "Engines",
            "Logger",
            "Checkpoint",
            "Loop ms",
            "Checkpoint ms",
            "Logger ms",
            "Stale",
        )
    }


def _bind_timeline(bundle: RuntimeBundle) -> dict[str, ProvenancedField]:
    dash = bundle.dashboard
    if dash is not None and dash.signal_history:
        fields: dict[str, ProvenancedField] = {
            "Available": ProvenancedField(
                value="yes",
                source_object="DashboardState",
                source_field="signal_history",
                timestamp=None,
                display_age=NA,
            )
        }
        for i, row in enumerate(dash.signal_history[-8:]):
            fields[f"Event[{i}]"] = ProvenancedField(
                value=(
                    f"{row.time_label} {row.direction} {row.result} pts={row.points}"
                ),
                source_object="DashboardState.signal_history",
                source_field=f"[{row.index}]",
                timestamp=None,
                display_age=NA,
            )
        return fields
    return {
        "Available": ProvenancedField(
            value="No timeline available",
            source_object="DashboardState.signal_history",
            source_field="signal_history",
            timestamp=None,
            display_age=NA,
        )
    }


def _bind_events(
    bundle: RuntimeBundle, *, ft: float | None
) -> dict[str, ProvenancedField]:
    dash = bundle.dashboard
    if dash is not None and dash.events:
        return {
            f"Event[{i}]": ProvenancedField(
                value=str(ev),
                source_object="DashboardState",
                source_field="events",
                timestamp=None,
                display_age=NA,
            )
            for i, ev in enumerate(tuple(dash.events)[-8:])
        }
    if bundle.transition_summaries:
        return {
            f"Event[{i}]": ProvenancedField(
                value=ev,
                source_object="structural_transition_journal",
                source_field="summary",
                timestamp=ft,
                display_age=format_age(bundle.now, ft) if ft is not None else NA,
            )
            for i, ev in enumerate(bundle.transition_summaries[-8:])
        }
    return {
        "Event[0]": unbound(
            reason=NA, source_object="DashboardState", source_field="events"
        )
    }
