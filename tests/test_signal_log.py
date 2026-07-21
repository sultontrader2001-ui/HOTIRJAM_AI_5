"""Tests for the file-based signal log writer."""

from __future__ import annotations

from pathlib import Path

import pytest

from hotirjam_ai5.dashboard.signal_log import SignalLogWriter


def test_write_appends_lines(tmp_path: Path) -> None:
    path = tmp_path / "logs" / "signals.log"
    writer = SignalLogWriter(path)
    writer.write("BUY_INTERNAL score=91")
    writer.write("SELL_INTERNAL score=89")
    assert path.read_text(encoding="utf-8").splitlines() == [
        "BUY_INTERNAL score=91",
        "SELL_INTERNAL score=89",
    ]


def test_write_creates_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "deeper" / "signals.log"
    SignalLogWriter(path).write("BUY_INTERNAL score=91")
    assert path.is_file()


def test_write_rejects_empty_message(tmp_path: Path) -> None:
    writer = SignalLogWriter(tmp_path / "signals.log")
    with pytest.raises(ValueError, match="non-empty"):
        writer.write("   ")
