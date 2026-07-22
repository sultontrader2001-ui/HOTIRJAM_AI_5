"""H-8.1A — INGRESS_POLL stderr gated; snapshot remains canonical."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from hotirjam_ai5.live_data import diagnostics as diag
from hotirjam_ai5.live_data.ingress import LiveTickIngress


def _tick_line(index: int) -> str:
    price = 20000.0 + index
    return json.dumps(
        {
            "timestamp": 1_700_000_000.0 + index,
            "symbol": "MNQ",
            "last_price": price,
            "bid": price - 0.25,
            "ask": price,
            "volume": 1.0,
        }
    )


def _ready_ingress(path: Path) -> LiveTickIngress:
    """Match production/test pattern: construct, then baseline poll at EOF."""
    ingress = LiveTickIngress(path)
    assert ingress.poll() == ()
    return ingress


def test_ingress_poll_stderr_default_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HOTIRJAM_INGRESS_POLL_STDERR", raising=False)
    monkeypatch.delenv("HOTIRJAM_INGRESS_DEBUG", raising=False)
    path = tmp_path / "ticks.ndjson"
    path.write_text("", encoding="utf-8")
    ingress = _ready_ingress(path)
    buf = io.StringIO()
    import hotirjam_ai5.live_data.ingress as ingress_mod

    monkeypatch.setattr(ingress_mod.sys, "stderr", buf)

    with path.open("a", encoding="utf-8") as handle:
        handle.write(_tick_line(0) + "\n")
    ticks = ingress.poll()
    assert len(ticks) == 1
    assert ingress.last_poll is not None
    assert ingress.last_poll.accepted_delta == 1
    assert "[INGRESS_POLL]" not in buf.getvalue()


def test_ingress_poll_stderr_on_explicit_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOTIRJAM_INGRESS_POLL_STDERR", "1")
    monkeypatch.delenv("HOTIRJAM_INGRESS_DEBUG", raising=False)
    path = tmp_path / "ticks.ndjson"
    path.write_text("", encoding="utf-8")
    ingress = _ready_ingress(path)
    buf = io.StringIO()
    import hotirjam_ai5.live_data.ingress as ingress_mod

    monkeypatch.setattr(ingress_mod.sys, "stderr", buf)

    with path.open("a", encoding="utf-8") as handle:
        handle.write(_tick_line(1) + "\n")
    ingress.poll()
    out = buf.getvalue()
    assert "[INGRESS_POLL]" in out
    assert "accepted_delta=1" in out
    assert ingress.last_poll is not None


def test_ingress_poll_stderr_on_ingress_debug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HOTIRJAM_INGRESS_POLL_STDERR", raising=False)
    monkeypatch.setenv("HOTIRJAM_INGRESS_DEBUG", "1")
    assert diag.ingress_poll_stderr_enabled() is True
    path = tmp_path / "ticks.ndjson"
    path.write_text("", encoding="utf-8")
    ingress = _ready_ingress(path)
    buf = io.StringIO()
    import hotirjam_ai5.live_data.ingress as ingress_mod

    monkeypatch.setattr(ingress_mod.sys, "stderr", buf)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_tick_line(2) + "\n")
    ingress.poll()
    assert "[INGRESS_POLL]" in buf.getvalue()


def test_snapshot_canonical_without_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HOTIRJAM_INGRESS_POLL_STDERR", raising=False)
    monkeypatch.delenv("HOTIRJAM_INGRESS_DEBUG", raising=False)
    path = tmp_path / "ticks.ndjson"
    path.write_text("", encoding="utf-8")
    ingress = _ready_ingress(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_tick_line(3) + "\n")
    ingress.poll()
    snap = ingress.last_poll
    assert snap is not None
    assert snap.gate == "OK"
    assert snap.tail_lines == 1
