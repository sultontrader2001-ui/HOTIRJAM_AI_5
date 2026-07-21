"""Liquidity Engine — produces LiquiditySnapshot from live DOM."""

from __future__ import annotations

import time
from collections.abc import Callable

from hotirjam_ai5.live_data.dom import DomSnapshot
from hotirjam_ai5.liquidity.classifier import classify_bias, imbalance_confidence
from hotirjam_ai5.liquidity.models import LiquiditySnapshot


class LiquidityEngine:
    """Stateful liquidity observation layer driven only by validated DOM.

    Never places orders or emits trade decisions.
    """

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time
        self._latest: LiquiditySnapshot | None = None

    def on_dom(self, snapshot: DomSnapshot) -> LiquiditySnapshot:
        """Update liquidity from one live DOM snapshot and return it."""
        total_bid = max(0, snapshot.total_bid_size)
        total_ask = max(0, snapshot.total_ask_size)
        best_bid = (
            snapshot.best_bid_size
            if snapshot.best_bid_size is not None
            else total_bid
        )
        best_ask = (
            snapshot.best_ask_size
            if snapshot.best_ask_size is not None
            else total_ask
        )
        best_bid = max(0, best_bid)
        best_ask = max(0, best_ask)

        imbalance = classify_bias(total_bid, total_ask)
        shift = classify_bias(best_bid, best_ask)
        confidence = imbalance_confidence(total_bid, total_ask)

        self._latest = LiquiditySnapshot(
            timestamp=self._clock(),
            liquidity_shift=shift.value,
            dom_imbalance=imbalance.value,
            confidence=confidence,
        )
        return self._latest

    def snapshot(self) -> LiquiditySnapshot | None:
        """Return the latest liquidity snapshot, or None if DOM never arrived."""
        return self._latest

    def clear(self) -> None:
        """Clear liquidity state when DOM becomes unavailable."""
        self._latest = None
