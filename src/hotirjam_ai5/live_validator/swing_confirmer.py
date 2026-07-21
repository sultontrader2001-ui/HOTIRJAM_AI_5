"""Simple confirmed-swing detector from closed OHLC bars (validator glue).

Not part of Objective Engine. Supplies ConfirmedSwing inputs only.
"""

from __future__ import annotations

from hotirjam_ai5.initiative import OhlcCandle
from hotirjam_ai5.objective import ConfirmedSwing


class SwingConfirmer:
    """Confirm fractal swing highs/lows once a bar closes on either side."""

    def __init__(self, *, max_swings: int = 40) -> None:
        if max_swings < 1:
            raise ValueError("max_swings must be positive")
        self._max_swings = max_swings
        self._highs: list[ConfirmedSwing] = []
        self._lows: list[ConfirmedSwing] = []
        self._history: list[OhlcCandle] = []

    @property
    def confirmed_highs(self) -> tuple[ConfirmedSwing, ...]:
        return tuple(self._highs)

    @property
    def confirmed_lows(self) -> tuple[ConfirmedSwing, ...]:
        return tuple(self._lows)

    def on_closed_candles(self, candles: tuple[OhlcCandle, ...]) -> None:
        """Append newly closed candles and confirm pivots when possible."""
        for candle in candles:
            self._history.append(candle)
            self._try_confirm()
        if len(self._history) > self._max_swings + 4:
            self._history = self._history[-(self._max_swings + 4) :]

    def _try_confirm(self) -> None:
        # Need left, center, right.
        if len(self._history) < 3:
            return
        left, center, right = self._history[-3], self._history[-2], self._history[-1]
        confirmed_at = right.timestamp if right.timestamp is not None else None

        if center.high > left.high and center.high > right.high:
            strength = _pivot_strength(center, left, right, high=True)
            self._highs.append(
                ConfirmedSwing(price=center.high, strength=strength, confirmed_at=confirmed_at)
            )
            if len(self._highs) > self._max_swings:
                self._highs = self._highs[-self._max_swings :]

        if center.low < left.low and center.low < right.low:
            strength = _pivot_strength(center, left, right, high=False)
            self._lows.append(
                ConfirmedSwing(price=center.low, strength=strength, confirmed_at=confirmed_at)
            )
            if len(self._lows) > self._max_swings:
                self._lows = self._lows[-self._max_swings :]


def _pivot_strength(
    center: OhlcCandle,
    left: OhlcCandle,
    right: OhlcCandle,
    *,
    high: bool,
) -> float:
    """0–100 strength from pivot prominence vs neighboring ranges."""
    if high:
        prominence = min(center.high - left.high, center.high - right.high)
        scale = max(center.high - center.low, 0.25)
    else:
        prominence = min(left.low - center.low, right.low - center.low)
        scale = max(center.high - center.low, 0.25)
    raw = (prominence / scale) * 50.0 + 40.0
    return max(0.0, min(100.0, raw))
