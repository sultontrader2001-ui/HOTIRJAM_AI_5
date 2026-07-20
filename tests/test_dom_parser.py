"""Tests for DomParser."""

from __future__ import annotations

import json

import pytest

from hotirjam_ai5.live_data.dom_parser import DomParseError, DomParser, canonicalize_instrument


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "source": "NT03",
        "schema_version": "1.0",
        "timestamp_utc": "2026-07-21T00:00:00.0000000Z",
        "instrument": "MNQ",
        "depth_levels": 10,
        "best_bid": 20100.0,
        "best_ask": 20100.25,
        "spread": 0.25,
        "mid": 20100.125,
        "bids": [{"price": 20100.0, "size": 12}, {"price": 20099.75, "size": 8}],
        "asks": [{"price": 20100.25, "size": 9}, {"price": 20100.5, "size": 7}],
        "bid_total_size": 20,
        "ask_total_size": 16,
        "dom_imbalance": 0.111,
        "delta_approx": 4,
        "status": "OK",
        "is_partial": False,
    }
    payload.update(overrides)
    return payload


def test_canonicalize_instrument() -> None:
    assert canonicalize_instrument("MNQ MAR 2025") == "MNQ"
    assert canonicalize_instrument("mnq") == "MNQ"


def test_parse_valid_payload() -> None:
    snap = DomParser().parse_payload(_payload())
    assert snap.instrument == "MNQ"
    assert snap.best_bid_size == 12
    assert snap.best_ask_size == 9
    assert snap.total_bid_size == 20
    assert snap.total_ask_size == 16
    assert snap.depth_levels == 10
    assert snap.status == "OK"


def test_parse_accepts_full_instrument_name() -> None:
    snap = DomParser().parse_payload(_payload(instrument="MNQ 09-26"))
    assert snap.instrument == "MNQ"


def test_parse_line() -> None:
    line = json.dumps(_payload())
    snap = DomParser().parse_line(line)
    assert snap.total_bid_size == 20


def test_empty_book_best_sizes_none() -> None:
    snap = DomParser().parse_payload(
        _payload(
            bids=[],
            asks=[],
            bid_total_size=0,
            ask_total_size=0,
            status="EMPTY",
            is_partial=True,
        )
    )
    assert snap.best_bid_size is None
    assert snap.best_ask_size is None


def test_reject_wrong_instrument() -> None:
    with pytest.raises(DomParseError, match="Unexpected instrument"):
        DomParser().parse_payload(_payload(instrument="ES"))


def test_reject_invalid_json() -> None:
    with pytest.raises(DomParseError, match="Invalid JSON"):
        DomParser().parse_line("{bad")
