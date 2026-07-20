"""Tests for NdjsonFileTail — live append only, no historical replay."""

from __future__ import annotations

from pathlib import Path

from hotirjam_ai5.live_data.ndjson_tail import NdjsonFileTail


def test_start_at_end_skips_existing_history(tmp_path: Path) -> None:
    path = tmp_path / "ticks.ndjson"
    path.write_text('{"n":1}\n{"n":2}\n', encoding="utf-8")
    tail = NdjsonFileTail(path)
    assert tail.poll() == ()
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"n":3}\n')
    assert tail.poll() == ('{"n":3}',)


def test_missing_file_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "missing.ndjson"
    assert NdjsonFileTail(path).poll() == ()


def test_file_created_after_start_arms_at_eof(tmp_path: Path) -> None:
    """When the file appears later, arm at EOF (no replay of bootstrap content)."""
    path = tmp_path / "ticks.ndjson"
    tail = NdjsonFileTail(path)
    assert tail.poll() == ()
    path.write_text('{"n":1}\n', encoding="utf-8")
    assert tail.poll() == ()
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"n":2}\n')
    assert tail.poll() == ('{"n":2}',)


def test_partial_line_waits_for_newline(tmp_path: Path) -> None:
    path = tmp_path / "ticks.ndjson"
    path.write_text("", encoding="utf-8")
    tail = NdjsonFileTail(path)
    assert tail.poll() == ()
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"n":1}')
    assert tail.poll() == ()
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n")
    assert tail.poll() == ('{"n":1}',)
