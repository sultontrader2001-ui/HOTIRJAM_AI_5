"""Deterministic consistency checks against subsequent market path (H-8.1)."""

from __future__ import annotations

from hotirjam_ai5.replay.models import ConfidenceLabel, MarketPoint, ModuleVerdict
from hotirjam_ai5.replay.parse import ParsedObservation

# Fixed certification constants — never tuned from intuition mid-session.
_TICK = 0.25
_TOL = _TICK * 2.0
_FLAT = _TICK
_BREAK_PROB_HIGH = 0.60
_BREAK_PROB_LOW = 0.35


def subsequent_window(
    market: tuple[MarketPoint, ...] | list[MarketPoint],
    *,
    after_time: float,
) -> tuple[MarketPoint, ...]:
    """Prices strictly after observation time, sorted by time (stable)."""
    pts = [p for p in market if p.time > after_time]
    pts.sort(key=lambda p: (p.time, p.price))
    return tuple(pts)


def _net_change(anchor: float, path: tuple[MarketPoint, ...]) -> float:
    if not path:
        return 0.0
    return path[-1].price - anchor


def _max_price(path: tuple[MarketPoint, ...]) -> float | None:
    if not path:
        return None
    return max(p.price for p in path)


def _min_price(path: tuple[MarketPoint, ...]) -> float | None:
    if not path:
        return None
    return min(p.price for p in path)


def validate_objective(
    parsed: ParsedObservation,
    path: tuple[MarketPoint, ...],
) -> tuple[ModuleVerdict, str]:
    """Objective consistent if subsequent path respects nearest H/L band."""
    if not path:
        return ModuleVerdict.PASS, "no subsequent path — objective not contradicted"
    if parsed.high is None and parsed.low is None:
        return ModuleVerdict.PASS, "no objective levels — nothing to contradict"
    hi = _max_price(path)
    lo = _min_price(path)
    assert hi is not None and lo is not None
    if parsed.high is not None and hi > parsed.high + _TOL:
        return ModuleVerdict.FAIL, f"broke above objective high {parsed.high}"
    if parsed.low is not None and lo < parsed.low - _TOL:
        return ModuleVerdict.FAIL, f"broke below objective low {parsed.low}"
    return ModuleVerdict.PASS, "path respected objective band"


def validate_initiative(
    parsed: ParsedObservation,
    path: tuple[MarketPoint, ...],
) -> tuple[ModuleVerdict, str]:
    """Initiative side should align with subsequent net drift."""
    if not path:
        return ModuleVerdict.PASS, "no subsequent path — initiative not contradicted"
    anchor = parsed.price if parsed.price is not None else path[0].price
    net = _net_change(anchor, path)
    side = parsed.initiative_side
    if side == "BUYER":
        if net >= -_FLAT:
            return ModuleVerdict.PASS, f"buyer initiative net={net:.2f}"
        return ModuleVerdict.FAIL, f"buyer initiative contradicted net={net:.2f}"
    if side == "SELLER":
        if net <= _FLAT:
            return ModuleVerdict.PASS, f"seller initiative net={net:.2f}"
        return ModuleVerdict.FAIL, f"seller initiative contradicted net={net:.2f}"
    if side in {"NONE", "UNKNOWN"}:
        if abs(net) <= _TOL * 2:
            return ModuleVerdict.PASS, f"neutral initiative net={net:.2f}"
        return ModuleVerdict.FAIL, f"neutral initiative saw large move net={net:.2f}"
    return ModuleVerdict.PASS, "initiative side unknown — not failed"


def validate_response(
    parsed: ParsedObservation,
    path: tuple[MarketPoint, ...],
) -> tuple[ModuleVerdict, str]:
    """Active counter-response expects adverse excursion; neutral does not."""
    if not path:
        return ModuleVerdict.PASS, "no subsequent path — response not contradicted"
    anchor = parsed.price if parsed.price is not None else path[0].price
    hi = _max_price(path)
    lo = _min_price(path)
    assert hi is not None and lo is not None
    up = hi - anchor
    down = anchor - lo

    if parsed.response_state in {"NEUTRAL", "ABSENT", "UNKNOWN"} and parsed.response_side == "NONE":
        return ModuleVerdict.PASS, "neutral/absent response"

    if parsed.response_side == "SELLER":
        if down >= _TICK:
            return ModuleVerdict.PASS, f"seller response pullback={down:.2f}"
        return ModuleVerdict.FAIL, "seller response without downside excursion"
    if parsed.response_side == "BUYER":
        if up >= _TICK:
            return ModuleVerdict.PASS, f"buyer response bounce={up:.2f}"
        return ModuleVerdict.FAIL, "buyer response without upside excursion"
    return ModuleVerdict.PASS, "response not contradicted"


def validate_continuation(
    parsed: ParsedObservation,
    path: tuple[MarketPoint, ...],
) -> tuple[ModuleVerdict, str]:
    """Strong continuation should not reverse; weak always PASS."""
    if not path:
        return ModuleVerdict.PASS, "no subsequent path — continuation not contradicted"
    if parsed.continuation_state == "WEAK" or parsed.continuation_score < 0.35:
        return ModuleVerdict.PASS, "weak continuation — not asserted"
    anchor = parsed.price if parsed.price is not None else path[0].price
    net = _net_change(anchor, path)
    side = parsed.continuation_side
    if side == "BUYER":
        if net >= -_FLAT:
            return ModuleVerdict.PASS, f"buyer continuation net={net:.2f}"
        return ModuleVerdict.FAIL, f"buyer continuation reversed net={net:.2f}"
    if side == "SELLER":
        if net <= _FLAT:
            return ModuleVerdict.PASS, f"seller continuation net={net:.2f}"
        return ModuleVerdict.FAIL, f"seller continuation reversed net={net:.2f}"
    return ModuleVerdict.PASS, "continuation side none/unknown"


def validate_break_capability(
    parsed: ParsedObservation,
    path: tuple[MarketPoint, ...],
) -> tuple[ModuleVerdict, str]:
    """High break probability expects breach; low expects hold."""
    if not path:
        return ModuleVerdict.PASS, "no subsequent path — break not contradicted"
    hi = _max_price(path)
    lo = _min_price(path)
    assert hi is not None and lo is not None
    prob = parsed.break_probability
    target = parsed.break_target_side

    broke_high = parsed.high is not None and hi > parsed.high + _TOL
    broke_low = parsed.low is not None and lo < parsed.low - _TOL

    if prob >= _BREAK_PROB_HIGH:
        if target == "HIGH" and broke_high:
            return ModuleVerdict.PASS, "high break prob realized above H"
        if target == "LOW" and broke_low:
            return ModuleVerdict.PASS, "high break prob realized below L"
        if target == "NONE":
            return ModuleVerdict.PASS, "high prob but no target — not failed"
        return ModuleVerdict.FAIL, "high break probability not realized"
    if prob <= _BREAK_PROB_LOW:
        if broke_high or broke_low:
            return ModuleVerdict.FAIL, "low break probability but level broke"
        return ModuleVerdict.PASS, "low break probability levels held"
    return ModuleVerdict.PASS, "mid break probability — not asserted"


def label_confidence(
    parsed: ParsedObservation,
    *,
    module_passes: int,
    module_total: int,
) -> tuple[ConfidenceLabel, str]:
    """Map confidence vs realized module pass rate."""
    if module_total <= 0:
        return ConfidenceLabel.CALIBRATED, "no modules"
    rate = module_passes / float(module_total)
    conf = parsed.confidence
    # Too High: claimed high confidence but weak outcomes
    if conf >= 0.70 and rate < 0.50:
        return ConfidenceLabel.TOO_HIGH, f"conf={conf:.2f} rate={rate:.2f}"
    # Too Low: claimed low confidence but strong outcomes
    if conf <= 0.30 and rate > 0.80:
        return ConfidenceLabel.TOO_LOW, f"conf={conf:.2f} rate={rate:.2f}"
    return ConfidenceLabel.CALIBRATED, f"conf={conf:.2f} rate={rate:.2f}"
