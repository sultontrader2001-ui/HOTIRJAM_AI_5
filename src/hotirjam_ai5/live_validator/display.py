"""Terminal display for Live Validator frames (observation only)."""

from __future__ import annotations

from hotirjam_ai5.live_validator.models import ValidatorFrame


def _fmt(value: float | None, *, digits: int = 2) -> str:
    if value is None:
        return "--"
    return f"{value:.{digits}f}"


def _join_reasons(reasons: tuple[str, ...], *, limit: int = 3) -> str:
    if not reasons:
        return "--"
    clipped = reasons[:limit]
    text = " | ".join(clipped)
    if len(reasons) > limit:
        text += f" (+{len(reasons) - limit} more)"
    return text


def render_validator_frame(frame: ValidatorFrame) -> str:
    """Render a full observation frame as plain text."""
    obj = frame.objective
    ini = frame.initiative
    resp = frame.response
    cont = frame.continuation
    brk = frame.break_capability

    lines = [
        "╔══════════════════════════════════════════════════════════════╗",
        "║           HOTIRJAM AI 5 — LIVE VALIDATOR (OBSERVE)           ║",
        "╚══════════════════════════════════════════════════════════════╝",
        "",
        f"Symbol            {frame.symbol}",
        f"Current Price     {_fmt(frame.current_price, digits=2)}",
        f"Timestamp         {_fmt(frame.timestamp, digits=3)}",
        f"Candles           {frame.candle_count}",
        f"Swing Highs/Lows  {frame.swing_high_count} / {frame.swing_low_count}",
        f"Decision          {frame.decision}",
        "",
        "── OBJECTIVE ──────────────────────────────────────────────────",
        f"  Nearest High    {_fmt(obj.nearest_high_price)}  "
        f"dist={_fmt(obj.nearest_high_distance_ticks)}  "
        f"str={_fmt(obj.nearest_high_strength)}",
        f"  Nearest Low     {_fmt(obj.nearest_low_price)}  "
        f"dist={_fmt(obj.nearest_low_distance_ticks)}  "
        f"str={_fmt(obj.nearest_low_strength)}",
        "",
        "── INITIATIVE ─────────────────────────────────────────────────",
        f"  Side            {ini.initiative_side.value}",
        f"  Score           {_fmt(ini.initiative_score)}  state={ini.state.value}  "
        f"conf={_fmt(ini.confidence)}",
        f"  Impulse/Mom/Cndl {_fmt(ini.impulse_score)} / "
        f"{_fmt(ini.momentum_score)} / {_fmt(ini.candle_strength_score)}",
        f"  Reasons         {_join_reasons(ini.reasons)}",
        "",
        "── RESPONSE ───────────────────────────────────────────────────",
        f"  Side            {resp.response_side.value}",
        f"  Strength        {_fmt(resp.response_strength)}  state={resp.response_state.value}",
        f"  Initiative Pres. {resp.initiative_preserved}  conf={_fmt(resp.confidence)}",
        f"  Reasons         {_join_reasons(resp.reasons)}",
        "",
        "── CONTINUATION ───────────────────────────────────────────────",
        f"  Side            {cont.continuation_side.value}",
        f"  Score           {_fmt(cont.continuation_score)}  state={cont.state.value}",
        f"  Pressure/Decay  {_fmt(cont.pressure_score)} / {_fmt(cont.momentum_decay)}",
        f"  Confidence      {_fmt(cont.confidence)}",
        f"  Reasons         {_join_reasons(cont.reasons)}",
        "",
        "── BREAK CAPABILITY ───────────────────────────────────────────",
        f"  Target          {brk.target_side.value} → {brk.target_type.value}",
        f"  Break Prob      {_fmt(brk.break_probability)}  state={brk.state.value}",
        f"  Pressure/Resist {_fmt(brk.pressure_score)} / {_fmt(brk.resistance_score)}",
        f"  Confidence      {_fmt(brk.confidence)}",
        f"  Reasons         {_join_reasons(brk.reasons)}",
        "",
        "Decision Engine: DISABLED",
        "Execution Engine: DISABLED",
        "No BUY / No SELL / No orders",
    ]
    return "\n".join(lines)
