"""Objective Engine input models — battlefield description only.

No trade direction, no BUY/SELL, no momentum or breakout concepts.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfirmedSwing:
    """A previously confirmed swing pivot (high or low).

    Strength is supplied by the confirmation source (0–100).
    The Objective Engine does not invent or recompute strength.
    """

    price: float
    strength: float
    confirmed_at: float | None = None


@dataclass(frozen=True, slots=True)
class ObjectiveInputs:
    """Read-only inputs for one Objective Engine evaluation.

    Confirmed swings are provided by an upstream confirmation source.
    This module only selects the nearest valid high and low.
    """

    current_price: float
    tick_size: float
    confirmed_highs: tuple[ConfirmedSwing, ...]
    confirmed_lows: tuple[ConfirmedSwing, ...]
    timestamp: float
