"""Terminal display for Live Validator — trader-oriented UI (observation only).

Presentation layer only. Does not alter engine calculations or scores.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hotirjam_ai5.continuation import ContinuationState
from hotirjam_ai5.initiative import InitiativeSide, InitiativeState
from hotirjam_ai5.live_validator.models import ValidatorFrame
from hotirjam_ai5.response import ResponseState


def _fmt(value: float | None, *, digits: int = 2) -> str:
    if value is None:
        return "--"
    return f"{value:.{digits}f}"


def _fmt_time(timestamp: float) -> str:
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%H:%M:%S UTC")
    except (OverflowError, OSError, ValueError):
        return _fmt(timestamp, digits=0)


def _rule(title: str = "") -> str:
    if title:
        return f"==============================\n{title}\n=============================="
    return "=============================="


def _active_objective(frame: ValidatorFrame) -> tuple[str, float | None, float | None, float | None]:
    """Pick the active objective for trader view from break target, else nearer side."""
    obj = frame.objective
    target = frame.break_capability.target_type.value
    if target == "HIGH" and obj.has_high:
        return (
            "HIGH",
            obj.nearest_high_price,
            obj.nearest_high_distance_ticks,
            obj.nearest_high_strength,
        )
    if target == "LOW" and obj.has_low:
        return (
            "LOW",
            obj.nearest_low_price,
            obj.nearest_low_distance_ticks,
            obj.nearest_low_strength,
        )

    # Fallback: nearer of the two when both exist.
    if obj.has_high and obj.has_low:
        high_d = obj.nearest_high_distance_ticks or float("inf")
        low_d = obj.nearest_low_distance_ticks or float("inf")
        if high_d <= low_d:
            return (
                "HIGH",
                obj.nearest_high_price,
                obj.nearest_high_distance_ticks,
                obj.nearest_high_strength,
            )
        return (
            "LOW",
            obj.nearest_low_price,
            obj.nearest_low_distance_ticks,
            obj.nearest_low_strength,
        )
    if obj.has_high:
        return (
            "HIGH",
            obj.nearest_high_price,
            obj.nearest_high_distance_ticks,
            obj.nearest_high_strength,
        )
    if obj.has_low:
        return (
            "LOW",
            obj.nearest_low_price,
            obj.nearest_low_distance_ticks,
            obj.nearest_low_strength,
        )
    return ("NONE", None, None, None)


def _momentum_direction(frame: ValidatorFrame) -> str:
    cont = frame.continuation.continuation_side.value
    if cont in {"BUYER", "SELLER"}:
        return cont
    ini = frame.initiative.initiative_side.value
    if ini in {"BUYER", "SELLER"}:
        return ini
    return "NONE"


def _momentum_state(frame: ValidatorFrame) -> tuple[str, str]:
    """Map existing snapshots to trader momentum labels. Display-only."""
    ini = frame.initiative
    cont = frame.continuation
    resp = frame.response
    direction = _momentum_direction(frame)

    if direction == "NONE" or (
        ini.initiative_side is InitiativeSide.NONE and cont.continuation_score < 20.0
    ):
        return "DEAD", "No clear directional pressure."

    if (
        cont.state is ContinuationState.STRONG
        and resp.initiative_preserved
        and cont.momentum_decay < 35.0
    ):
        return "STRONG", f"Strong {direction.lower()} continuation holding."

    if cont.momentum_decay >= 60.0 or cont.state is ContinuationState.WEAK:
        return "WEAKENING", f"{direction.title()} pressure is fading."

    if not resp.initiative_preserved or resp.response_state is ResponseState.STRONG:
        return "WEAKENING", "Opposing response is challenging initiative."

    if ini.state is InitiativeState.STRONG or cont.state is ContinuationState.MEDIUM:
        return "BUILDING", f"{direction.title()} momentum is building."

    return "BUILDING", f"{direction.title()} pressure developing."


def _ai_thinking(frame: ValidatorFrame) -> list[str]:
    """At most 4 concise trader-facing bullets. Display-only synthesis."""
    bullets: list[str] = []
    ini = frame.initiative
    resp = frame.response
    cont = frame.continuation
    brk = frame.break_capability
    target, price, distance, _strength = _active_objective(frame)
    direction = _momentum_direction(frame)
    mom_state, _ = _momentum_state(frame)

    if direction == "BUYER":
        bullets.append("Strong buyer initiative" if ini.initiative_score >= 60 else "Buyer initiative present")
    elif direction == "SELLER":
        bullets.append("Strong seller initiative" if ini.initiative_score >= 60 else "Seller initiative present")
    else:
        bullets.append("No clear initiative")

    if resp.response_state is ResponseState.FAILED and direction != "NONE":
        opp = "Buyer" if direction == "SELLER" else "Seller"
        bullets.append(f"{opp} response failed")
    elif resp.response_state is ResponseState.STRONG:
        bullets.append("Strong opposing response")
    elif not resp.initiative_preserved:
        bullets.append("Initiative under pressure")

    if mom_state == "STRONG":
        bullets.append("Momentum increasing")
    elif mom_state == "WEAKENING":
        bullets.append("Momentum fading")
    elif mom_state == "BUILDING":
        bullets.append("Momentum building")

    if target != "NONE" and distance is not None:
        bullets.append(f"Objective only {_fmt(distance, digits=1)} ticks away")
    elif brk.break_probability >= 70.0:
        bullets.append("Break probability elevated")

    # Cap at 4 unique-ish lines.
    unique: list[str] = []
    for b in bullets:
        if b not in unique:
            unique.append(b)
        if len(unique) >= 4:
            break
    while len(unique) < 1:
        unique.append("Waiting for market structure")
    return unique[:4]


def _feed_status_label(feed_status: str | None, frame: ValidatorFrame) -> str:
    if feed_status:
        return feed_status
    return "LIVE" if frame.current_price is not None else "WAITING"


def render_trader_view(
    frame: ValidatorFrame,
    *,
    feed_status: str | None = None,
) -> str:
    """Default trader-oriented screen."""
    target, obj_price, distance, strength = _active_objective(frame)
    direction = _momentum_direction(frame)
    mom_state, mom_explain = _momentum_state(frame)
    brk = frame.break_capability
    thinking = _ai_thinking(frame)

    lines = [
        "==============================",
        "HOTIRJAM AI 5",
        "LIVE ANALYSIS",
        "==============================",
        f"Symbol            {frame.symbol}",
        f"Current Price     {_fmt(frame.current_price)}",
        f"Current Time      {_fmt_time(frame.timestamp)}",
        f"Feed Status       {_feed_status_label(feed_status, frame)}",
        "==============================",
        "OBJECTIVE",
        "==============================",
        f"Target            {target}",
        f"Objective Price   {_fmt(obj_price)}",
        f"Distance (ticks)  {_fmt(distance, digits=1)}",
        f"Objective Strength {_fmt(strength, digits=1)}",
        "==============================",
        "MARKET MOMENTUM",
        "==============================",
        f"Direction         {direction}",
        f"State             {mom_state}",
        f"                  {mom_explain}",
        "==============================",
        "BREAK ANALYSIS",
        "==============================",
        f"Target            {brk.target_type.value}",
        f"Break Probability {_fmt(brk.break_probability, digits=1)}",
        f"State             {brk.state.value}",
        "==============================",
        "AI THINKING",
        "==============================",
    ]
    for bullet in thinking:
        lines.append(f"• {bullet}")
    lines.extend(
        [
            "==============================",
            "Decision Engine   DISABLED",
            "Execution Engine  DISABLED",
            "Observation Mode  No Orders",
            "",
            "Press D — Developer View",
        ]
    )
    return "\n".join(lines)


def render_developer_view(
    frame: ValidatorFrame,
    *,
    feed_status: str | None = None,
) -> str:
    """Optional developer overlay — raw scores still available, not default."""
    obj = frame.objective
    ini = frame.initiative
    resp = frame.response
    cont = frame.continuation
    brk = frame.break_capability

    def reasons(rs: tuple[str, ...]) -> str:
        if not rs:
            return "--"
        return " | ".join(rs[:4])

    lines = [
        _rule("HOTIRJAM AI 5"),
        "LIVE ANALYSIS — DEVELOPER VIEW",
        _rule(),
        f"Symbol            {frame.symbol}",
        f"Current Price     {_fmt(frame.current_price)}",
        f"Current Time      {_fmt_time(frame.timestamp)}",
        f"Feed Status       {_feed_status_label(feed_status, frame)}",
        f"Candles / Swings  {frame.candle_count}  H:{frame.swing_high_count} L:{frame.swing_low_count}",
        _rule("OBJECTIVE"),
        f"High {_fmt(obj.nearest_high_price)} dist={_fmt(obj.nearest_high_distance_ticks)} "
        f"str={_fmt(obj.nearest_high_strength)}",
        f"Low  {_fmt(obj.nearest_low_price)} dist={_fmt(obj.nearest_low_distance_ticks)} "
        f"str={_fmt(obj.nearest_low_strength)}",
        _rule("INITIATIVE"),
        f"Side {ini.initiative_side.value}  score={_fmt(ini.initiative_score)}  "
        f"state={ini.state.value}  conf={_fmt(ini.confidence)}",
        f"Impulse/Mom/Cndl {_fmt(ini.impulse_score)} / {_fmt(ini.momentum_score)} / "
        f"{_fmt(ini.candle_strength_score)}",
        f"Reasons {reasons(ini.reasons)}",
        _rule("RESPONSE"),
        f"Side {resp.response_side.value}  strength={_fmt(resp.response_strength)}  "
        f"state={resp.response_state.value}  preserved={resp.initiative_preserved}  "
        f"conf={_fmt(resp.confidence)}",
        f"Reasons {reasons(resp.reasons)}",
        _rule("CONTINUATION"),
        f"Side {cont.continuation_side.value}  score={_fmt(cont.continuation_score)}  "
        f"state={cont.state.value}",
        f"Pressure/Decay {_fmt(cont.pressure_score)} / {_fmt(cont.momentum_decay)}  "
        f"conf={_fmt(cont.confidence)}",
        f"Reasons {reasons(cont.reasons)}",
        _rule("BREAK CAPABILITY"),
        f"Target {brk.target_side.value} → {brk.target_type.value}",
        f"Break Prob {_fmt(brk.break_probability)}  state={brk.state.value}",
        f"Pressure/Resist {_fmt(brk.pressure_score)} / {_fmt(brk.resistance_score)}  "
        f"conf={_fmt(brk.confidence)}",
        f"Reasons {reasons(brk.reasons)}",
        _rule(),
        "Decision Engine   DISABLED",
        "Execution Engine  DISABLED",
        "Observation Mode  No Orders",
        "",
        "Press D — Trader View",
    ]
    return "\n".join(lines)


def render_validator_frame(
    frame: ValidatorFrame,
    *,
    developer_mode: bool = False,
    feed_status: str | None = None,
) -> str:
    """Render observation frame. Default is Trader View."""
    if developer_mode:
        return render_developer_view(frame, feed_status=feed_status)
    return render_trader_view(frame, feed_status=feed_status)
