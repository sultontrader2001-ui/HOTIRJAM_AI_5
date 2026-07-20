"""Tests for LiveDomIngress."""

from __future__ import annotations

import json
from pathlib import Path

from hotirjam_ai5.live_data.dom_ingress import LiveDomIngress


def _dom_line(*, instrument: str = "MNQ") -> str:
    return json.dumps(
        {
            "source": "NT03",
            "schema_version": "1.0",
            "timestamp_utc": "2026-07-21T00:00:00.0000000Z",
            "instrument": instrument,
            "depth_levels": 5,
            "best_bid": 20100.0,
            "best_ask": 20100.25,
            "spread": 0.25,
            "mid": 20100.125,
            "bids": [{"price": 20100.0, "size": 3}],
            "asks": [{"price": 20100.25, "size": 4}],
            "bid_total_size": 3,
            "ask_total_size": 4,
            "dom_imbalance": -0.14,
            "delta_approx": -1,
            "status": "OK",
            "is_partial": False,
        }
    )


def test_dom_ingress_reads_only_new_valid_snapshots(tmp_path: Path) -> None:
    path = tmp_path / "mnq_dom.ndjson"
    path.write_text(_dom_line() + "\n", encoding="utf-8")
    ingress = LiveDomIngress(path)
    assert ingress.poll() == ()

    with path.open("a", encoding="utf-8") as handle:
        handle.write(_dom_line() + "\n")
        handle.write("not-json\n")
        handle.write(_dom_line(instrument="ES") + "\n")

    snaps = ingress.poll()
    assert len(snaps) == 1
    assert snaps[0].best_bid_size == 3
    assert ingress.accepted_count == 1
    assert ingress.skipped_count == 2
