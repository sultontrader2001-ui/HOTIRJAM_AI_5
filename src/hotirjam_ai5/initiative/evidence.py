"""Independent evidence channels for Initiative observation."""

from __future__ import annotations

from collections.abc import Sequence

from hotirjam_ai5.initiative.initiative_models import (
    CandleStrengthResult,
    ImpulseResult,
    ImpulseSide,
    InitiativeEvidence,
    MomentumResult,
    OhlcCandle,
)
from hotirjam_ai5.objective import ObjectiveSnapshot


def _directional(side: ImpulseSide, score: float) -> tuple[float, float]:
    if side is ImpulseSide.BUYER:
        return score, 0.0
    if side is ImpulseSide.SELLER:
        return 0.0, score
    return 0.0, 0.0


def measure_liquidity(
    candles: Sequence[OhlcCandle],
) -> tuple[float, float, float, tuple[str, ...]]:
    """Volume-weighted directional yield from recent bars."""
    valid = [c for c in candles if c.high >= c.low and c.volume >= 0.0]
    if not valid:
        return 0.0, 0.0, 0.0, ("No liquidity evidence",)

    window = valid[-5:]
    buy_vol = 0.0
    sell_vol = 0.0
    total = 0.0
    for candle in window:
        total += candle.volume
        if candle.close > candle.open:
            buy_vol += candle.volume
        elif candle.close < candle.open:
            sell_vol += candle.volume

    if total <= 0.0:
        # Flat volume — use directional bar counts as weak liquidity proxy.
        buy_n = sum(1 for c in window if c.close > c.open)
        sell_n = sum(1 for c in window if c.close < c.open)
        n = max(1, len(window))
        buy = (buy_n / n) * 40.0
        sell = (sell_n / n) * 40.0
        score = max(buy, sell)
        return score, buy, sell, ("Liquidity from directional bar share",)

    buy = min(100.0, (buy_vol / total) * 100.0)
    sell = min(100.0, (sell_vol / total) * 100.0)
    score = max(buy, sell)
    return (
        score,
        buy,
        sell,
        (f"Buy volume share {buy:.1f}", f"Sell volume share {sell:.1f}"),
    )


def measure_energy(candles: Sequence[OhlcCandle], *, tick_size: float) -> tuple[float, tuple[str, ...]]:
    """Activity / energy from range and volume."""
    valid = [c for c in candles if c.high >= c.low]
    if not valid or tick_size <= 0.0:
        return 0.0, ("No energy evidence",)

    window = valid[-5:]
    avg_range_ticks = sum((c.high - c.low) / tick_size for c in window) / len(window)
    avg_volume = sum(max(0.0, c.volume) for c in window) / len(window)
    # 8 ticks average range ≈ 60; volume 20 ≈ 40.
    range_part = min(60.0, (avg_range_ticks / 8.0) * 60.0)
    volume_part = min(40.0, (avg_volume / 20.0) * 40.0)
    score = max(0.0, min(100.0, range_part + volume_part))
    return score, (
        f"Avg range {avg_range_ticks:.1f} ticks",
        f"Avg volume {avg_volume:.1f}",
    )


def build_evidence(
    *,
    impulse: ImpulseResult,
    momentum: MomentumResult,
    candles: CandleStrengthResult,
    ohlc: Sequence[OhlcCandle],
    tick_size: float,
    objectives: ObjectiveSnapshot | None,
) -> tuple[InitiativeEvidence, float, float, tuple[str, ...]]:
    """Build structured evidence and independent buyer/seller intensities."""
    reasons: list[str] = []
    reasons.extend(impulse.reasons)
    reasons.extend(momentum.reasons)
    reasons.extend(candles.reasons)

    force_b, force_s = _directional(impulse.side, impulse.score)
    motion_b, motion_s = _directional(momentum.direction, momentum.score)
    pressure_b, pressure_s = _directional(candles.direction, candles.score)
    liq_score, liq_b, liq_s, liq_reasons = measure_liquidity(ohlc)
    reasons.extend(liq_reasons)
    energy, energy_reasons = measure_energy(ohlc, tick_size=tick_size)
    reasons.extend(energy_reasons)

    # Energy amplifies the currently active side(s); never chooses side alone.
    energy_b = energy if force_b + motion_b + pressure_b + liq_b > 0 else 0.0
    energy_s = energy if force_s + motion_s + pressure_s + liq_s > 0 else 0.0
    if energy_b == 0.0 and energy_s == 0.0 and energy > 0.0:
        # Contested/noisy activity — share energy equally without choosing a side.
        energy_b = energy * 0.5
        energy_s = energy * 0.5

    # Context is Objective presence only — confidence channel, never intensity.
    context = 0.0
    if objectives is not None and objectives.is_complete:
        context = 25.0
        reasons.append("Objective map complete — context confidence available")
    elif objectives is None:
        reasons.append("Objective unavailable — initiative uses market evidence only")
    else:
        reasons.append("Objective incomplete — context confidence withheld")

    evidence = InitiativeEvidence(
        force=max(force_b, force_s),
        motion=max(motion_b, motion_s),
        pressure=max(pressure_b, pressure_s),
        liquidity=liq_score,
        energy=energy,
        context=context,
    )

    buyer = (
        0.25 * force_b
        + 0.20 * motion_b
        + 0.20 * pressure_b
        + 0.20 * liq_b
        + 0.15 * energy_b
    )
    seller = (
        0.25 * force_s
        + 0.20 * motion_s
        + 0.20 * pressure_s
        + 0.20 * liq_s
        + 0.15 * energy_s
    )
    buyer = max(0.0, min(100.0, buyer))
    seller = max(0.0, min(100.0, seller))
    return evidence, buyer, seller, tuple(reasons)
