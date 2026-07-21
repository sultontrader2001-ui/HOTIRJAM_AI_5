"""Time-based OHLC bar builder from live ticks (validator glue only)."""

from __future__ import annotations

from hotirjam_ai5.initiative import OhlcCandle
from hotirjam_ai5.live_data.tick import LiveTick


class TickBarBuilder:
    """Aggregate ticks into fixed-duration OHLC candles.

    Closed bars are retained for engine lookback. The in-progress bar is
    exposed separately and is never treated as confirmed until closed.
    """

    def __init__(
        self,
        *,
        bar_seconds: float = 1.0,
        max_bars: int = 120,
    ) -> None:
        if bar_seconds <= 0.0:
            raise ValueError("bar_seconds must be positive")
        if max_bars < 2:
            raise ValueError("max_bars must be at least 2")
        self._bar_seconds = bar_seconds
        self._max_bars = max_bars
        self._closed: list[OhlcCandle] = []
        self._bucket_start: float | None = None
        self._open: float | None = None
        self._high: float | None = None
        self._low: float | None = None
        self._close: float | None = None
        self._volume: float = 0.0

    @property
    def closed_candles(self) -> tuple[OhlcCandle, ...]:
        return tuple(self._closed)

    @property
    def forming_candle(self) -> OhlcCandle | None:
        if self._open is None:
            return None
        assert self._high is not None and self._low is not None and self._close is not None
        return OhlcCandle(
            open=self._open,
            high=self._high,
            low=self._low,
            close=self._close,
            volume=self._volume,
            timestamp=self._bucket_start,
        )

    def on_tick(self, tick: LiveTick) -> tuple[OhlcCandle, ...]:
        """Ingest one tick; return any candles that just closed."""
        price = tick.last_price
        ts = tick.timestamp
        bucket = (ts // self._bar_seconds) * self._bar_seconds
        newly_closed: list[OhlcCandle] = []

        if self._bucket_start is None:
            self._start_bar(bucket, price, tick.volume)
            return ()

        if bucket > self._bucket_start:
            closed = self._finalize_bar()
            if closed is not None:
                newly_closed.append(closed)
                self._closed.append(closed)
                if len(self._closed) > self._max_bars:
                    self._closed = self._closed[-self._max_bars :]
            self._start_bar(bucket, price, tick.volume)
        else:
            assert self._high is not None and self._low is not None
            self._high = max(self._high, price)
            self._low = min(self._low, price)
            self._close = price
            self._volume += max(0.0, tick.volume)

        return tuple(newly_closed)

    def candles_for_engines(self) -> tuple[OhlcCandle, ...]:
        """Closed bars plus forming bar when present (engines need recent path)."""
        forming = self.forming_candle
        if forming is None:
            return self.closed_candles
        return (*self.closed_candles, forming)

    def _start_bar(self, bucket_start: float, price: float, volume: float) -> None:
        self._bucket_start = bucket_start
        self._open = price
        self._high = price
        self._low = price
        self._close = price
        self._volume = max(0.0, volume)

    def _finalize_bar(self) -> OhlcCandle | None:
        if self._open is None or self._bucket_start is None:
            return None
        assert self._high is not None and self._low is not None and self._close is not None
        return OhlcCandle(
            open=self._open,
            high=self._high,
            low=self._low,
            close=self._close,
            volume=self._volume,
            timestamp=self._bucket_start,
        )
