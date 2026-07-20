"""Tests for TickParser."""

from __future__ import annotations

import pytest

from hotirjam_ai5.live_data.tick_parser import TickParseError, TickParser


def _valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "timestamp": 1_700_000_000.0,
        "symbol": "MNQ",
        "last_price": 20100.5,
        "bid": 20100.25,
        "ask": 20100.5,
        "volume": 2.0,
    }
    payload.update(overrides)
    return payload


def test_parse_valid_payload() -> None:
    tick = TickParser().parse_payload(_valid_payload())
    assert tick.symbol == "MNQ"
    assert tick.last_price == 20100.5
    assert tick.bid == 20100.25
    assert tick.ask == 20100.5
    assert tick.volume == 2.0
    assert tick.spread == 0.25


def test_parse_line_round_trip() -> None:
    line = (
        '{"timestamp":1700000000.0,"symbol":"MNQ","last_price":20100.5,'
        '"bid":20100.25,"ask":20100.5,"volume":2.0}'
    )
    tick = TickParser().parse_line(line)
    assert tick.last_price == 20100.5


def test_reject_wrong_symbol() -> None:
    with pytest.raises(TickParseError, match="Unexpected symbol"):
        TickParser().parse_payload(_valid_payload(symbol="ES"))


def test_reject_invalid_spread() -> None:
    with pytest.raises(TickParseError, match="Invalid spread"):
        TickParser().parse_payload(_valid_payload(bid=100.5, ask=100.0))


def test_reject_missing_fields() -> None:
    with pytest.raises(TickParseError, match="Missing fields"):
        TickParser().parse_payload({"symbol": "MNQ"})


def test_reject_non_positive_price() -> None:
    with pytest.raises(TickParseError, match="last_price"):
        TickParser().parse_payload(_valid_payload(last_price=0))


def test_reject_invalid_json() -> None:
    with pytest.raises(TickParseError, match="Invalid JSON"):
        TickParser().parse_line("{not-json")
