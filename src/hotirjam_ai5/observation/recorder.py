"""Extract ObservationCycle fields from published snapshots (read-only)."""

from __future__ import annotations

from typing import Any

from hotirjam_ai5.observation.models import ObservationCycle

_NA = "N/A"
_UNWIRED = "UNWIRED"


def _enum_val(value: object) -> str:
    if value is None:
        return _NA
    return str(getattr(value, "value", value))


def _reasons(obj: object, *, limit: int = 3) -> str:
    reasons = getattr(obj, "reasons", None)
    if not reasons:
        return _NA
    return " | ".join(str(r) for r in tuple(reasons)[:limit])


def record_from_frame(
    frame: Any,
    *,
    cycle_id: int,
    dashboard: Any | None = None,
) -> ObservationCycle:
    """Build one cycle from an existing ValidatorFrame (+ optional DashboardState).

    Never evaluates engines. Never mutates inputs.
    """
    obj = getattr(frame, "objective", None)
    ini = getattr(frame, "initiative", None)
    rsp = getattr(frame, "response", None)
    cont = getattr(frame, "continuation", None)
    brk = getattr(frame, "break_capability", None)

    if obj is not None:
        objective = (
            f"H={getattr(obj, 'nearest_high_price', None)} "
            f"L={getattr(obj, 'nearest_low_price', None)}"
        )
    else:
        objective = _UNWIRED

    if ini is not None:
        initiative = (
            f"{_enum_val(getattr(ini, 'dominant_side', None))} "
            f"{_enum_val(getattr(ini, 'initiative_state', None))} "
            f"c={float(getattr(ini, 'confidence', 0.0)):.2f}"
        )
        evidence_obj = getattr(ini, "evidence", None)
        if evidence_obj is not None:
            evidence = (
                f"force={getattr(evidence_obj, 'force', _NA)} "
                f"energy={getattr(evidence_obj, 'energy', _NA)} "
                f"liq={getattr(evidence_obj, 'liquidity', _NA)}"
            )
        else:
            evidence = _NA
        ini_conf = float(getattr(ini, "confidence", 0.0) or 0.0)
    else:
        initiative = _UNWIRED
        evidence = _UNWIRED
        ini_conf = 0.0

    if rsp is not None:
        response = (
            f"{_enum_val(getattr(rsp, 'response_side', None))} "
            f"{_enum_val(getattr(rsp, 'response_state', None))} "
            f"s={float(getattr(rsp, 'response_strength', 0.0)):.2f}"
        )
        rsp_conf = float(getattr(rsp, "confidence", 0.0) or 0.0)
    else:
        response = _UNWIRED
        rsp_conf = 0.0

    if cont is not None:
        continuation = (
            f"{_enum_val(getattr(cont, 'continuation_side', None))} "
            f"{_enum_val(getattr(cont, 'state', None))} "
            f"sc={float(getattr(cont, 'continuation_score', 0.0)):.2f}"
        )
        cont_conf = float(getattr(cont, "confidence", 0.0) or 0.0)
    else:
        continuation = _UNWIRED
        cont_conf = 0.0

    if brk is not None:
        break_capability = (
            f"{_enum_val(getattr(brk, 'target_side', None))} "
            f"{_enum_val(getattr(brk, 'state', None))} "
            f"p={float(getattr(brk, 'break_probability', 0.0)):.2f}"
        )
        brk_conf = float(getattr(brk, "confidence", 0.0) or 0.0)
    else:
        break_capability = _UNWIRED
        brk_conf = 0.0

    confidence = f"{max(ini_conf, rsp_conf, cont_conf, brk_conf):.2f}"

    market_state = _UNWIRED
    no_trade_reason = _UNWIRED
    decision = str(getattr(frame, "decision", "DISABLED") or "DISABLED")

    if dashboard is not None:
        ms = getattr(dashboard, "market_state", None)
        if ms is not None:
            market_state = str(getattr(ms, "state", _UNWIRED))
        td = getattr(dashboard, "trade_decision", None)
        if td is not None:
            decision = str(getattr(td, "decision", decision) or decision)
            reason = getattr(td, "reason", None)
            if reason:
                no_trade_reason = str(reason)
    if no_trade_reason == _UNWIRED and decision:
        no_trade_reason = f"decision={decision}"

    price = getattr(frame, "current_price", None)
    return ObservationCycle(
        cycle_id=cycle_id,
        time=float(getattr(frame, "timestamp", 0.0) or 0.0),
        objective=objective.strip(),
        initiative=initiative.strip(),
        response=response.strip(),
        continuation=continuation.strip(),
        break_capability=break_capability.strip(),
        confidence=confidence,
        market_state=market_state,
        evidence=evidence,
        no_trade_reason=no_trade_reason,
        decision=decision,
        symbol=str(getattr(frame, "symbol", _NA) or _NA),
        price=_NA if price is None else f"{float(price):.2f}",
    )
