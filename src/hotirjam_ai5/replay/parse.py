"""Parse observation record strings — pure, deterministic (H-8.1)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_H_RE = re.compile(r"H=([^\s]+)")
_L_RE = re.compile(r"L=([^\s]+)")
_C_RE = re.compile(r"\bc=([0-9.]+)")
_P_RE = re.compile(r"\bp=([0-9.]+)")
_SC_RE = re.compile(r"\bsc=([0-9.]+)")


def _parse_float(token: str | None) -> float | None:
    if token is None:
        return None
    text = token.strip()
    if text in {"", "None", "N/A", "UNWIRED", "nan", "NaN"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class ParsedObservation:
    high: float | None
    low: float | None
    initiative_side: str  # BUYER | SELLER | NONE | UNKNOWN
    response_side: str
    response_state: str
    continuation_side: str
    continuation_state: str
    continuation_score: float
    break_target_side: str
    break_state: str
    break_probability: float
    confidence: float
    price: float | None


def parse_observation(
    *,
    objective: str,
    initiative: str,
    response: str,
    continuation: str,
    break_capability: str,
    confidence: str,
    price: str,
) -> ParsedObservation:
    """Extract structured fields from H-8.0 string records."""
    hm = _H_RE.search(objective)
    lm = _L_RE.search(objective)
    high = _parse_float(hm.group(1) if hm else None)
    low = _parse_float(lm.group(1) if lm else None)

    ini_u = initiative.upper()
    if "BUYER" in ini_u:
        initiative_side = "BUYER"
    elif "SELLER" in ini_u:
        initiative_side = "SELLER"
    elif "NONE" in ini_u:
        initiative_side = "NONE"
    else:
        initiative_side = "UNKNOWN"

    rsp_u = response.upper()
    if "BUYER" in rsp_u:
        response_side = "BUYER"
    elif "SELLER" in rsp_u:
        response_side = "SELLER"
    else:
        response_side = "NONE"
    if "NEUTRAL" in rsp_u:
        response_state = "NEUTRAL"
    elif "ABSENT" in rsp_u:
        response_state = "ABSENT"
    elif "ACTIVE" in rsp_u or "STRONG" in rsp_u:
        response_state = "ACTIVE"
    else:
        response_state = "UNKNOWN"

    cont_u = continuation.upper()
    if "BUYER" in cont_u:
        continuation_side = "BUYER"
    elif "SELLER" in cont_u:
        continuation_side = "SELLER"
    else:
        continuation_side = "NONE"
    if "WEAK" in cont_u:
        continuation_state = "WEAK"
    elif "STRONG" in cont_u or "CONTINUING" in cont_u:
        continuation_state = "STRONG"
    else:
        continuation_state = "UNKNOWN"
    sc_m = _SC_RE.search(continuation)
    continuation_score = float(sc_m.group(1)) if sc_m else 0.0

    brk_u = break_capability.upper()
    tokens = brk_u.split()
    break_target_side = "NONE"
    if tokens:
        head = tokens[0]
        if head in {"HIGH", "LOW", "NONE"}:
            break_target_side = head
        elif "HIGH" in brk_u:
            break_target_side = "HIGH"
        elif "LOW" in brk_u:
            break_target_side = "LOW"
    if "INSUFFICIENT" in brk_u or "WEAK" in brk_u:
        break_state = "WEAK"
    elif "SUFFICIENT" in brk_u or "READY" in brk_u:
        break_state = "STRONG"
    else:
        break_state = "UNKNOWN"
    p_m = _P_RE.search(break_capability)
    break_probability = float(p_m.group(1)) if p_m else 0.0

    conf = _parse_float(confidence)
    if conf is None:
        c_m = _C_RE.search(initiative)
        conf = float(c_m.group(1)) if c_m else 0.0
    if conf > 1.0:
        conf = conf / 100.0

    return ParsedObservation(
        high=high,
        low=low,
        initiative_side=initiative_side,
        response_side=response_side,
        response_state=response_state,
        continuation_side=continuation_side,
        continuation_state=continuation_state,
        continuation_score=continuation_score,
        break_target_side=break_target_side,
        break_state=break_state,
        break_probability=break_probability,
        confidence=max(0.0, min(1.0, conf)),
        price=_parse_float(price),
    )
