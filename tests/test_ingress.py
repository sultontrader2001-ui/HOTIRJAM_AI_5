"""Tests for LiveTickIngress."""

from __future__ import annotations

import json
from pathlib import Path

from hotirjam_ai5.live_data.ingress import LiveTickIngress


def _tick_line(index: int, *, symbol: str = "MNQ") -> str:
    price = 20000.0 + index
    return json.dumps(
        {
            "timestamp": 1_700_000_000.0 + index,
            "symbol": symbol,
            "last_price": price,
            "bid": price - 0.25,
            "ask": price,
            "volume": 1.0 + index,
        }
    )


def test_ingress_reads_only_new_valid_ticks(tmp_path: Path) -> None:
    path = tmp_path / "mnq_ticks.ndjson"
    path.write_text(_tick_line(0) + "\n" + _tick_line(1) + "\n", encoding="utf-8")
    ingress = LiveTickIngress(path)
    assert ingress.poll() == ()

    with path.open("a", encoding="utf-8") as handle:
        handle.write(_tick_line(2) + "\n")
        handle.write("not-json\n")
        handle.write(_tick_line(3, symbol="ES") + "\n")
        handle.write(_tick_line(4) + "\n")

    ticks = ingress.poll()
    assert len(ticks) == 2
    assert ticks[0].last_price == 20002.0
    assert ticks[1].last_price == 20004.0
    assert ingress.accepted_count == 2
    assert ingress.skipped_count == 2
