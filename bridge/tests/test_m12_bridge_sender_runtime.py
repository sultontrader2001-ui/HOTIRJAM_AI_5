"""M1.2 Bridge Sender runtime tests — no network, no AI."""

from __future__ import annotations

import io
import json
import threading
import time
from pathlib import Path

from hotirjam_bridge.contracts import Channel
from hotirjam_bridge.sender.app import main
from hotirjam_bridge.sender.runtime import TickSenderRuntime
from hotirjam_bridge.sender.tail import NdjsonTail
from hotirjam_bridge.sender.validate_tick import TickValidationError, validate_nt01_tick


def _tick_line(*, i: int, ts: float | None = None) -> str:
    timestamp = 1_700_000_000.0 + (ts if ts is not None else float(i))
    px = 18000.0 + (i % 17) * 0.25
    payload = {
        "timestamp": timestamp,
        "symbol": "MNQ",
        "last_price": px,
        "bid": px - 0.25,
        "ask": px + 0.25,
        "volume": 1.0,
    }
    return json.dumps(payload, separators=(",", ":")) + "\n"


def test_validate_rejects_bad_tick() -> None:
    try:
        validate_nt01_tick({"symbol": "MNQ"}, expected_symbol="MNQ")
        assert False, "expected TickValidationError"
    except TickValidationError:
        pass


def test_tail_skips_incomplete_line(tmp_path: Path) -> None:
    path = tmp_path / "mnq_ticks.ndjson"
    path.write_text(_tick_line(i=0), encoding="utf-8")
    tail = NdjsonTail(path, start_at_eof=False)
    assert len(tail.poll()) == 1
    # Incomplete line (no trailing newline) must not be emitted.
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"timestamp":1')
    assert tail.poll() == []
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            ',"symbol":"MNQ","last_price":1,"bid":1,"ask":1.25,"volume":1}\n'
        )
    lines = tail.poll()
    assert len(lines) == 1


def test_tail_recovers_after_journal_truncate(tmp_path: Path) -> None:
    """After first live lines, a shrink/replace must not park the offset past EOF."""
    path = tmp_path / "mnq_ticks.ndjson"
    path.write_text(_tick_line(i=0) + _tick_line(i=1), encoding="utf-8")
    tail = NdjsonTail(path, start_at_eof=True)
    assert tail.poll() == []

    with path.open("a", encoding="utf-8") as handle:
        handle.write(_tick_line(i=2))
    assert len(tail.poll()) == 1
    stuck_offset = tail.offset
    assert stuck_offset > 0

    # NT01 / retention style: replace journal with a shorter file, then append.
    path.write_text(_tick_line(i=10), encoding="utf-8")
    assert path.stat().st_size < stuck_offset
    assert tail.poll() == []  # re-armed at new EOF

    with path.open("a", encoding="utf-8") as handle:
        handle.write(_tick_line(i=11))
    got = tail.poll()
    assert len(got) == 1
    assert '"last_price":' in got[0]


def test_tail_byte_offsets_with_crlf(tmp_path: Path) -> None:
    """Windows NT journals may use CRLF; offsets must stay byte-accurate."""
    path = tmp_path / "mnq_ticks.ndjson"
    line0 = _tick_line(i=0).replace("\n", "\r\n")
    path.write_bytes(line0.encode("utf-8"))
    tail = NdjsonTail(path, start_at_eof=True)
    assert tail.offset == path.stat().st_size
    assert tail.poll() == []

    line1 = _tick_line(i=1).replace("\n", "\r\n")
    with path.open("ab") as handle:
        handle.write(line1.encode("utf-8"))
    got = tail.poll()
    assert len(got) == 1
    assert got[0].endswith("}") and "\r" not in got[0]
    assert tail.offset == path.stat().st_size


def test_tail_start_at_eof_then_append_nonzero_file(tmp_path: Path) -> None:
    """Non-empty journal at startup must still catch later appends (Windows case)."""
    path = tmp_path / "mnq_ticks.ndjson"
    path.write_text(_tick_line(i=0) * 50, encoding="utf-8")
    tail = NdjsonTail(path, start_at_eof=True)
    assert tail.poll() == []
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_tick_line(i=99))
    got = tail.poll()
    assert len(got) == 1
    assert '"last_price":' in got[0]


def test_sender_catches_new_tick_immediately(tmp_path: Path) -> None:
    path = tmp_path / "mnq_ticks.ndjson"
    path.write_text("", encoding="utf-8")
    log = io.StringIO()
    runtime = TickSenderRuntime(
        tick_file=path,
        start_at_eof=True,
        poll_interval=0.01,
        log_stream=log,
        sleep=lambda _s: None,
    )

    # First poll: empty.
    assert runtime.poll_once() == []

    with path.open("a", encoding="utf-8") as handle:
        handle.write(_tick_line(i=1))
        handle.flush()

    got = runtime.poll_once()
    assert len(got) == 1
    assert got[0].ch == Channel.TICK.value
    assert got[0].seq == 1
    assert "seq=1" in log.getvalue()
    assert '"ch":"tick"' in log.getvalue()


def test_sender_clean_stop_like_ctrl_c(tmp_path: Path) -> None:
    path = tmp_path / "mnq_ticks.ndjson"
    path.write_text("", encoding="utf-8")
    log = io.StringIO()
    runtime = TickSenderRuntime(
        tick_file=path,
        start_at_eof=True,
        poll_interval=0.01,
        log_stream=log,
        sleep=lambda _s: time.sleep(0.01),
    )

    def _stop_soon() -> None:
        time.sleep(0.05)
        runtime.request_stop()

    thread = threading.Thread(target=_stop_soon, daemon=True)
    thread.start()
    stats = runtime.run()
    thread.join(timeout=2.0)
    assert "[BRIDGE_SENDER] stop" in log.getvalue()
    assert stats.ticks_accepted == 0


def test_sender_reads_1000_ticks_continuously(tmp_path: Path) -> None:
    path = tmp_path / "mnq_ticks.ndjson"
    with path.open("w", encoding="utf-8") as handle:
        for i in range(1000):
            handle.write(_tick_line(i=i))

    log = io.StringIO()
    runtime = TickSenderRuntime(
        tick_file=path,
        start_at_eof=False,
        poll_interval=0.0,
        max_ticks=1000,
        log_stream=log,
        sleep=lambda _s: None,
    )
    stats = runtime.run()
    assert stats.ticks_accepted == 1000
    assert stats.last_seq == 1000
    assert stats.malformed == 0
    assert runtime.envelopes[0].seq == 1
    assert runtime.envelopes[-1].seq == 1000
    assert runtime.envelopes[-1].payload["symbol"] == "MNQ"


def test_cli_max_ticks_and_log_file(tmp_path: Path) -> None:
    tick_file = tmp_path / "mnq_ticks.ndjson"
    with tick_file.open("w", encoding="utf-8") as handle:
        for i in range(5):
            handle.write(_tick_line(i=i))
    log_file = tmp_path / "sender_runtime.log"
    code = main(
        [
            "--tick-file",
            str(tick_file),
            "--from-start",
            "--max-ticks",
            "5",
            "--poll",
            "0",
            "--log-file",
            str(log_file),
        ]
    )
    assert code == 0
    text = log_file.read_text(encoding="utf-8")
    assert "network=OFF" in text
    assert "seq=5" in text
    assert "accepted=5" in text
