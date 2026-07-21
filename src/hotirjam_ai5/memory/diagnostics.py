"""Market Memory Diagnostics (Sprint 43) — read-only analysis.

Reads MemoryItem history only. Never appends, never mutates, never feeds
Trade Decision. Band windows are diagnostic observation scales only
(Sprint 40 examples) — not trading thresholds.
"""

from __future__ import annotations

from collections.abc import Sequence

from hotirjam_ai5.memory.diagnostics_models import (
    BandSummary,
    ConsensusStatus,
    ConsensusSummary,
    MemoryBandName,
    MemoryDiagnosticsReport,
    SourceSummary,
    StoreDiagnosticsSummary,
    TimelineEvent,
)
from hotirjam_ai5.memory.memory_store import MarketMemoryStore
from hotirjam_ai5.memory.memory_types import MemoryItem, MemorySource

# Diagnostic observation windows (examples from Sprint 40 — not decision gates).
DIAG_FAST_SECONDS = 10.0
DIAG_MEDIUM_SECONDS = 30.0
DIAG_SLOW_SECONDS = 60.0

TIMELINE_LIMIT = 20

_BUY_SIDE = frozenset({"BUY", "UP"})
_SELL_SIDE = frozenset({"SELL", "DOWN"})
_NEUTRAL_SIDE = frozenset({"NEUTRAL", "NO_TRADE", "NONE", "—"})


def normalize_direction(direction: str) -> str:
    """Map heterogeneous source directions to BUY / SELL / NEUTRAL."""
    text = direction.strip().upper()
    if text in _BUY_SIDE:
        return "BUY"
    if text in _SELL_SIDE:
        return "SELL"
    return "NEUTRAL"


def strength_to_pct(strength: float) -> float:
    """Map heterogeneous MemoryItem.strength to a 0–100 display scale."""
    if strength <= 1.0:
        return _clamp(strength * 100.0)
    return _clamp(strength)


def confidence_to_pct(confidence: float) -> float:
    """Map MemoryItem.confidence [0,1] to 0–100."""
    return _clamp(confidence * 100.0)


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def items_in_band(
    items: Sequence[MemoryItem],
    *,
    as_of: float,
    window_seconds: float,
) -> tuple[MemoryItem, ...]:
    """Return items with timestamp in (as_of - window, as_of]."""
    if window_seconds <= 0:
        raise ValueError("window_seconds must be positive")
    start = as_of - window_seconds
    return tuple(item for item in items if start < item.timestamp <= as_of)


def summarize_band(
    items: Sequence[MemoryItem],
    *,
    name: MemoryBandName,
    window_seconds: float,
    as_of: float,
) -> BandSummary:
    """Build Direction / Strength / Confidence / Persistence for one band."""
    band_items = items_in_band(items, as_of=as_of, window_seconds=window_seconds)
    buy = sell = neutral = 0
    strength_vals: list[float] = []
    conf_vals: list[float] = []
    norms: list[str] = []
    for item in band_items:
        norm = normalize_direction(item.direction)
        norms.append(norm)
        if norm == "BUY":
            buy += 1
        elif norm == "SELL":
            sell += 1
        else:
            neutral += 1
        strength_vals.append(strength_to_pct(item.strength))
        conf_vals.append(confidence_to_pct(item.confidence))

    if not band_items:
        direction = "NEUTRAL"
        strength = 0.0
        confidence = 0.0
        persistence = 0.0
    else:
        direction = _majority_direction(buy, sell, neutral)
        strength = sum(strength_vals) / len(strength_vals)
        confidence = sum(conf_vals) / len(conf_vals)
        matching = sum(1 for n in norms if n == direction)
        persistence = 100.0 * matching / len(norms)

    return BandSummary(
        name=name,
        window_seconds=window_seconds,
        direction=direction,
        buy_count=buy,
        sell_count=sell,
        neutral_count=neutral,
        strength=round(strength, 1),
        confidence=round(confidence, 1),
        persistence=round(persistence, 1),
        record_count=len(band_items),
    )


def _majority_direction(buy: int, sell: int, neutral: int) -> str:
    """Dominant normalized side; ties involving two sides → NEUTRAL."""
    if buy == 0 and sell == 0:
        return "NEUTRAL"
    if buy > sell and buy > neutral:
        return "BUY"
    if sell > buy and sell > neutral:
        return "SELL"
    if neutral >= buy and neutral >= sell:
        return "NEUTRAL"
    if buy == sell:
        return "NEUTRAL"
    return "BUY" if buy > sell else "SELL"


def summarize_sources(items: Sequence[MemoryItem]) -> tuple[SourceSummary, ...]:
    """Per-source current direction and averages over the full buffer."""
    rows: list[SourceSummary] = []
    for source in MemorySource:
        src_items = [item for item in items if item.source is source]
        if not src_items:
            rows.append(
                SourceSummary(
                    source=source,
                    current_direction="NEUTRAL",
                    average_strength=0.0,
                    average_confidence=0.0,
                    record_count=0,
                    last_update=None,
                )
            )
            continue
        last = src_items[-1]
        avg_s = sum(strength_to_pct(i.strength) for i in src_items) / len(src_items)
        avg_c = sum(confidence_to_pct(i.confidence) for i in src_items) / len(src_items)
        rows.append(
            SourceSummary(
                source=source,
                current_direction=normalize_direction(last.direction),
                average_strength=round(avg_s, 1),
                average_confidence=round(avg_c, 1),
                record_count=len(src_items),
                last_update=last.timestamp,
            )
        )
    return tuple(rows)


def build_timeline(
    items: Sequence[MemoryItem],
    *,
    limit: int = TIMELINE_LIMIT,
) -> tuple[TimelineEvent, ...]:
    """Last N memory events in chronological order (oldest → newest)."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    recent = list(items[-limit:])
    return tuple(
        TimelineEvent(
            timestamp=item.timestamp,
            source=item.source,
            direction=normalize_direction(item.direction),
            strength=round(strength_to_pct(item.strength), 1),
            confidence=round(confidence_to_pct(item.confidence), 1),
        )
        for item in recent
    )


def compute_consensus(bands: Sequence[BandSummary]) -> ConsensusSummary:
    """Consensus direction, confidence, cross-band agreement, and status."""
    if len(bands) != 3:
        raise ValueError("consensus requires exactly three band summaries")
    fast, medium, slow = bands[0], bands[1], bands[2]
    dirs = (fast.direction, medium.direction, slow.direction)

    buy_votes = sum(1 for d in dirs if d == "BUY")
    sell_votes = sum(1 for d in dirs if d == "SELL")
    if buy_votes > sell_votes and buy_votes > 0:
        direction = "BUY"
    elif sell_votes > buy_votes and sell_votes > 0:
        direction = "SELL"
    else:
        direction = "NEUTRAL"

    conf = (fast.confidence + medium.confidence + slow.confidence) / 3.0

    # Pairwise band agreement (3 pairs) blended with mean confidence.
    pairs = ((0, 1), (0, 2), (1, 2))
    pair_hits = sum(1 for i, j in pairs if dirs[i] == dirs[j])
    pair_frac = pair_hits / 3.0
    agreement = 100.0 * (0.7 * pair_frac + 0.3 * (conf / 100.0))
    agreement = round(_clamp(agreement), 1)

    if direction == "NEUTRAL" or agreement < 50.0:
        status = ConsensusStatus.UNCERTAIN
    elif agreement >= 80.0:
        status = ConsensusStatus.ALIGNED
    else:
        status = ConsensusStatus.MIXED

    return ConsensusSummary(
        direction=direction,
        confidence=round(conf, 1),
        agreement=agreement,
        status=status,
        fast_direction=fast.direction,
        medium_direction=medium.direction,
        slow_direction=slow.direction,
    )


def summarize_store(
    store: MarketMemoryStore,
    items: Sequence[MemoryItem],
) -> StoreDiagnosticsSummary:
    """Memory size, ring usage, oldest/newest, per-source counts, append rate."""
    size = len(items)
    capacity = store.capacity
    usage = 0.0 if capacity == 0 else 100.0 * size / capacity
    counts = {source: 0 for source in MemorySource}
    oldest: float | None = None
    newest: float | None = None
    for item in items:
        counts[item.source] += 1
        if oldest is None or item.timestamp < oldest:
            oldest = item.timestamp
        if newest is None or item.timestamp > newest:
            newest = item.timestamp
    rate: float | None = None
    if oldest is not None and newest is not None and newest > oldest and size > 1:
        rate = (size - 1) / (newest - oldest)
    return StoreDiagnosticsSummary(
        memory_size=size,
        capacity=capacity,
        ring_buffer_usage=round(usage, 1),
        oldest_record=oldest,
        newest_record=newest,
        records_per_source=counts,
        average_append_rate=None if rate is None else round(rate, 3),
    )


def build_memory_diagnostics(
    store: MarketMemoryStore,
    *,
    as_of: float | None = None,
    fast_seconds: float = DIAG_FAST_SECONDS,
    medium_seconds: float = DIAG_MEDIUM_SECONDS,
    slow_seconds: float = DIAG_SLOW_SECONDS,
    timeline_limit: int = TIMELINE_LIMIT,
) -> MemoryDiagnosticsReport:
    """Build a full diagnostics report by reading the store (no writes)."""
    items = store.items()
    if as_of is None:
        as_of = items[-1].timestamp if items else 0.0

    bands = (
        summarize_band(
            items,
            name=MemoryBandName.FAST,
            window_seconds=fast_seconds,
            as_of=as_of,
        ),
        summarize_band(
            items,
            name=MemoryBandName.MEDIUM,
            window_seconds=medium_seconds,
            as_of=as_of,
        ),
        summarize_band(
            items,
            name=MemoryBandName.SLOW,
            window_seconds=slow_seconds,
            as_of=as_of,
        ),
    )
    return MemoryDiagnosticsReport(
        bands=bands,
        sources=summarize_sources(items),
        consensus=compute_consensus(bands),
        timeline=build_timeline(items, limit=timeline_limit),
        store=summarize_store(store, items),
        as_of=as_of,
    )
