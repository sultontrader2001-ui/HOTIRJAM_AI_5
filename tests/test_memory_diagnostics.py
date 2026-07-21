"""Tests for Market Memory Diagnostics (Sprint 43) — read-only."""

from __future__ import annotations

import pytest

from hotirjam_ai5.memory import (
    BandSummary,
    ConsensusStatus,
    MarketMemoryStore,
    MemoryBandName,
    MemoryItem,
    MemorySource,
    build_memory_diagnostics,
    build_timeline,
    compute_consensus,
    normalize_direction,
    strength_to_pct,
    summarize_band,
)


def _item(
    ts: float,
    *,
    source: MemorySource = MemorySource.PHYSICS,
    direction: str = "UP",
    strength: float = 0.8,
    confidence: float = 0.9,
) -> MemoryItem:
    return MemoryItem(
        timestamp=ts,
        source=source,
        direction=direction,
        strength=strength,
        confidence=confidence,
    )


def test_normalize_direction_maps_sides() -> None:
    assert normalize_direction("UP") == "BUY"
    assert normalize_direction("BUY") == "BUY"
    assert normalize_direction("DOWN") == "SELL"
    assert normalize_direction("SELL") == "SELL"
    assert normalize_direction("NO_TRADE") == "NEUTRAL"
    assert normalize_direction("NEUTRAL") == "NEUTRAL"


def test_strength_to_pct_scales_unit_and_caps() -> None:
    assert strength_to_pct(0.5) == pytest.approx(50.0)
    assert strength_to_pct(80.0) == pytest.approx(80.0)
    assert strength_to_pct(250.0) == pytest.approx(100.0)


def test_band_summary_direction_counts_and_persistence() -> None:
    items = [
        _item(1.0, direction="UP"),
        _item(2.0, direction="UP"),
        _item(3.0, direction="DOWN"),
        _item(4.0, direction="UP"),
        _item(5.0, direction="NEUTRAL"),
    ]
    band = summarize_band(
        items,
        name=MemoryBandName.FAST,
        window_seconds=10.0,
        as_of=5.0,
    )
    assert band.direction == "BUY"
    assert band.buy_count == 3
    assert band.sell_count == 1
    assert band.neutral_count == 1
    assert band.persistence == pytest.approx(60.0)
    assert 0.0 <= band.strength <= 100.0
    assert 0.0 <= band.confidence <= 100.0
    assert band.record_count == 5


def test_band_window_excludes_older_records() -> None:
    items = [
        _item(1.0, direction="DOWN"),
        _item(2.0, direction="DOWN"),
        _item(20.0, direction="UP"),
        _item(21.0, direction="UP"),
    ]
    band = summarize_band(
        items,
        name=MemoryBandName.FAST,
        window_seconds=10.0,
        as_of=21.0,
    )
    assert band.record_count == 2
    assert band.direction == "BUY"
    assert band.buy_count == 2
    assert band.sell_count == 0


def test_consensus_aligned_when_all_bands_buy() -> None:
    bands = (
        BandSummary(
            name=MemoryBandName.FAST,
            window_seconds=10,
            direction="BUY",
            buy_count=10,
            sell_count=0,
            neutral_count=0,
            strength=80,
            confidence=90,
            persistence=95,
            record_count=10,
        ),
        BandSummary(
            name=MemoryBandName.MEDIUM,
            window_seconds=30,
            direction="BUY",
            buy_count=20,
            sell_count=1,
            neutral_count=0,
            strength=75,
            confidence=88,
            persistence=90,
            record_count=21,
        ),
        BandSummary(
            name=MemoryBandName.SLOW,
            window_seconds=60,
            direction="BUY",
            buy_count=40,
            sell_count=2,
            neutral_count=0,
            strength=70,
            confidence=85,
            persistence=88,
            record_count=42,
        ),
    )
    consensus = compute_consensus(bands)
    assert consensus.direction == "BUY"
    assert consensus.fast_direction == "BUY"
    assert consensus.medium_direction == "BUY"
    assert consensus.slow_direction == "BUY"
    assert consensus.agreement >= 80.0
    assert consensus.status is ConsensusStatus.ALIGNED


def test_consensus_uncertain_when_bands_disagree() -> None:
    bands = (
        BandSummary(
            name=MemoryBandName.FAST,
            window_seconds=10,
            direction="SELL",
            buy_count=0,
            sell_count=5,
            neutral_count=0,
            strength=60,
            confidence=50,
            persistence=100,
            record_count=5,
        ),
        BandSummary(
            name=MemoryBandName.MEDIUM,
            window_seconds=30,
            direction="BUY",
            buy_count=8,
            sell_count=2,
            neutral_count=0,
            strength=55,
            confidence=50,
            persistence=80,
            record_count=10,
        ),
        BandSummary(
            name=MemoryBandName.SLOW,
            window_seconds=60,
            direction="BUY",
            buy_count=15,
            sell_count=5,
            neutral_count=0,
            strength=50,
            confidence=50,
            persistence=75,
            record_count=20,
        ),
    )
    consensus = compute_consensus(bands)
    assert consensus.direction == "BUY"
    assert consensus.fast_direction == "SELL"
    assert consensus.agreement < 50.0 or consensus.status is ConsensusStatus.UNCERTAIN
    # Pairwise 1/3 ≈ 33% blended with conf 50% → ~38–41% region
    assert 30.0 <= consensus.agreement <= 50.0
    assert consensus.status is ConsensusStatus.UNCERTAIN


def test_timeline_ordering_last_n() -> None:
    store = MarketMemoryStore(capacity=100)
    for i in range(30):
        store.append(_item(float(i), direction="UP" if i % 2 == 0 else "DOWN"))
    timeline = build_timeline(store.items(), limit=20)
    assert len(timeline) == 20
    assert timeline[0].timestamp == 10.0
    assert timeline[-1].timestamp == 29.0
    assert all(
        timeline[i].timestamp <= timeline[i + 1].timestamp
        for i in range(len(timeline) - 1)
    )


def test_snapshot_generation_and_store_diagnostics() -> None:
    store = MarketMemoryStore(capacity=50)
    t0 = 1000.0
    for i in range(25):
        store.append(
            _item(
                t0 + i,
                source=MemorySource.PHYSICS,
                direction="UP",
                strength=0.7,
                confidence=0.8,
            )
        )
        store.append(
            _item(
                t0 + i,
                source=MemorySource.LIQUIDITY,
                direction="BUY",
                strength=0.6,
                confidence=0.7,
            )
        )
    report = build_memory_diagnostics(store, as_of=t0 + 24)
    assert len(report.bands) == 3
    assert report.bands[0].name is MemoryBandName.FAST
    assert report.bands[1].name is MemoryBandName.MEDIUM
    assert report.bands[2].name is MemoryBandName.SLOW
    assert len(report.sources) == 5
    physics = next(s for s in report.sources if s.source is MemorySource.PHYSICS)
    assert physics.record_count == 25
    assert physics.current_direction == "BUY"
    assert physics.last_update == t0 + 24
    assert report.store.memory_size == 50
    assert report.store.ring_buffer_usage == pytest.approx(100.0)
    assert report.store.oldest_record == t0
    assert report.store.newest_record == t0 + 24
    assert report.store.records_per_source[MemorySource.PHYSICS] == 25
    assert report.store.average_append_rate is not None
    assert report.store.average_append_rate > 0
    assert len(report.timeline) == 20
    # Read-only: building diagnostics must not change store size.
    assert store.size == 50


def test_diagnostics_do_not_write_to_memory() -> None:
    store = MarketMemoryStore(capacity=10)
    store.append(_item(1.0))
    before = store.items()
    _ = build_memory_diagnostics(store, as_of=1.0)
    assert store.items() == before
