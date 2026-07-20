"""Tests for temporary ingress diagnostics and parse logging."""

from __future__ import annotations

import io
import json
from pathlib import Path

from hotirjam_ai5.live_data.diagnostics import IngressDiagnostics
from hotirjam_ai5.live_data.ingress import LiveTickIngress


def test_ingress_diagnostics_log_path_lines_parse_and_emit(tmp_path: Path) -> None:
    path = tmp_path / "mnq_ticks.ndjson"
    path.write_text("", encoding="utf-8")
    buffer = io.StringIO()
    diagnostics = IngressDiagnostics(enabled=True, stream=buffer)
    ingress = LiveTickIngress(path, diagnostics=diagnostics)
    assert ingress.poll() == ()

    good = json.dumps(
        {
            "timestamp": 1_700_000_000.0,
            "symbol": "MNQ",
            "last_price": 20100.0,
            "bid": 20099.75,
            "ask": 20100.0,
            "volume": 1.0,
        }
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(good + "\n")
        handle.write("not-json\n")

    ticks = ingress.poll()
    assert len(ticks) == 1
    text = buffer.getvalue()
    assert "Opened file path:" in text
    assert "Line read:" in text
    assert "Parse success / tick emitted" in text
    assert "Parse failure:" in text
