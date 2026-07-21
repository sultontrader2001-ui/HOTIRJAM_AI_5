"""Market Memory score influence (Sprint 44) — secondary adjustment only.

Reads Memory Diagnostics. Never invents BUY/SELL decisions.
Primary scores still come from Assessment/Feed/State/Behavior/Physics/Liquidity.
"""

from __future__ import annotations

from typing import Final

from hotirjam_ai5.memory.diagnostics_models import (
    ConsensusStatus,
    MemoryDiagnosticsReport,
)
from hotirjam_ai5.trade_decision.models import MemoryScoreInfluence

# Hard caps — Memory must never dominate the 100-point primary score.
MEMORY_MAX_BOOST: Final[int] = 5
MEMORY_MAX_OPPOSE: Final[int] = 3
MEMORY_MIN_AGREEMENT: Final[float] = 80.0


def _clamp_score(value: int) -> int:
    return max(0, min(100, value))


def _mean_persistence(report: MemoryDiagnosticsReport) -> float:
    bands = report.bands
    if not bands:
        return 0.0
    return sum(band.persistence for band in bands) / len(bands)


def compute_memory_deltas(
    report: MemoryDiagnosticsReport | None,
) -> tuple[int, int, bool]:
    """Return (buy_delta, sell_delta, applied) from diagnostics only."""
    if report is None:
        return 0, 0, False

    consensus = report.consensus
    if consensus.status is not ConsensusStatus.ALIGNED:
        return 0, 0, False
    if consensus.direction not in {"BUY", "SELL"}:
        return 0, 0, False
    if consensus.agreement < MEMORY_MIN_AGREEMENT:
        return 0, 0, False

    persistence = _mean_persistence(report)
    scale = (
        (consensus.agreement / 100.0)
        * (persistence / 100.0)
        * (consensus.confidence / 100.0)
    )
    boost = max(1, min(MEMORY_MAX_BOOST, int(round(MEMORY_MAX_BOOST * scale))))
    oppose = min(MEMORY_MAX_OPPOSE, max(0, boost // 2))
    if boost >= 2 and oppose == 0:
        oppose = 1

    if consensus.direction == "BUY":
        return boost, -oppose, True
    return -oppose, boost, True


def apply_memory_score_influence(
    *,
    original_buy_score: int,
    original_sell_score: int,
    report: MemoryDiagnosticsReport | None,
) -> MemoryScoreInfluence:
    """Adjust primary scores with a capped Memory influence."""
    if report is None:
        return MemoryScoreInfluence.none(original_buy_score, original_sell_score)

    buy_delta, sell_delta, applied = compute_memory_deltas(report)
    adjusted_buy = _clamp_score(original_buy_score + buy_delta)
    adjusted_sell = _clamp_score(original_sell_score + sell_delta)
    persistence = _mean_persistence(report)
    max_abs = max(abs(buy_delta), abs(sell_delta))
    influence_pct = (
        round(100.0 * max_abs / MEMORY_MAX_BOOST, 1) if MEMORY_MAX_BOOST else 0.0
    )
    return MemoryScoreInfluence(
        original_buy_score=original_buy_score,
        original_sell_score=original_sell_score,
        buy_delta=buy_delta,
        sell_delta=sell_delta,
        adjusted_buy_score=adjusted_buy,
        adjusted_sell_score=adjusted_sell,
        consensus=report.consensus.direction,
        agreement=round(report.consensus.agreement, 1),
        persistence=round(persistence, 1),
        confidence=round(report.consensus.confidence, 1),
        status=report.consensus.status.value,
        influence_pct=influence_pct,
        applied=applied,
    )
