"""H-6.7 retention policy tests — AI-safe storage only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hotirjam_ai5.live_data.ingress import LiveTickIngress
from hotirjam_ai5.live_validator.certification_dashboard import AuditLog
from hotirjam_ai5.live_validator.idc_performance import render_performance_page
from hotirjam_ai5.live_validator.logger import SnapshotLogger
from hotirjam_ai5.live_validator.models import ValidatorFrame
from hotirjam_ai5.live_validator.pipeline import ArchitecturePipeline
from hotirjam_ai5.objective import ConfirmedSwing
from hotirjam_ai5.objective_diagnostics import (
    ObjectiveDiagnosticsInputs,
    PersistentStructuralHierarchy,
)
from hotirjam_ai5.retention import (
    enforce_ndjson_size_limit,
    load_retention_config,
    reset_retention_config_for_tests,
    reset_retention_stats_for_tests,
    rotate_log_if_needed,
)
from hotirjam_ai5.retention.stats import RetentionSnapshot, get_retention_event_count


TICK = 0.25


@pytest.fixture(autouse=True)
def _reset_retention(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    reset_retention_config_for_tests()
    reset_retention_stats_for_tests()
    cfg = tmp_path / "retention.json"
    cfg.write_text(
        json.dumps(
            {
                "objective_journal_max_entries": 10_000,
                "hierarchy_max_versions": 500,
                "snapshot_log_max_file_size_mb": 100,
                "tick_ndjson_max_file_size_mb": 200,
                "dom_ndjson_max_file_size_mb": 200,
                "audit_events_max_entries": 50_000,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HOTIRJAM_RETENTION_CONFIG", str(cfg))
    yield
    reset_retention_config_for_tests()
    reset_retention_stats_for_tests()


def _swing(price: float, strength: float, at: float) -> ConfirmedSwing:
    return ConfirmedSwing(price=price, strength=strength, confirmed_at=at)


def _inputs(
    *,
    highs: tuple[ConfirmedSwing, ...] = (),
    lows: tuple[ConfirmedSwing, ...] = (),
    timestamp: float = 10.0,
) -> ObjectiveDiagnosticsInputs:
    return ObjectiveDiagnosticsInputs(
        current_price=100.0,
        tick_size=TICK,
        confirmed_highs=highs,
        confirmed_lows=lows,
        timestamp=timestamp,
    )


def test_load_retention_config_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reset_retention_config_for_tests()
    path = tmp_path / "custom.json"
    path.write_text(
        json.dumps({"hierarchy_max_versions": 7, "objective_journal_max_entries": 20}),
        encoding="utf-8",
    )
    monkeypatch.setenv("HOTIRJAM_RETENTION_CONFIG", str(path))
    cfg = load_retention_config()
    assert cfg.hierarchy_max_versions == 7
    assert cfg.objective_journal_max_entries == 20
    assert cfg.hierarchy_journal_cap == 7


def test_hierarchy_journal_not_pruned_by_retention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Live journal/checkpoint contents must not change for AI safety."""
    reset_retention_config_for_tests()
    path = tmp_path / "ret.json"
    path.write_text(
        json.dumps(
            {
                "objective_journal_max_entries": 100,
                "hierarchy_max_versions": 5,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HOTIRJAM_RETENTION_CONFIG", str(path))

    hierarchy = PersistentStructuralHierarchy()
    highs: list[ConfirmedSwing] = []
    lows: list[ConfirmedSwing] = []
    for i in range(12):
        highs.append(_swing(110.0 - i * 0.25, 80.0, float(i) + 1.0))
        lows.append(_swing(90.0 + i * 0.25, 80.0, float(i) + 1.5))
        hierarchy.evaluate(
            _inputs(
                highs=tuple(highs[-3:]),
                lows=tuple(lows[-3:]),
                timestamp=float(i) + 10.0,
            )
        )

    assert len(hierarchy.journal) > 5
    sequences = [item.sequence for item in hierarchy.journal]
    assert sequences == sorted(sequences)


def test_hierarchy_checkpoint_preserves_full_journal(tmp_path: Path) -> None:
    checkpoint = tmp_path / "hierarchy.json"
    original = PersistentStructuralHierarchy(checkpoint_path=checkpoint)
    for i in range(8):
        original.evaluate(
            _inputs(
                highs=(_swing(110.0 - i * 0.25, 80.0, float(i) + 1.0),),
                lows=(_swing(90.0 + i * 0.25, 80.0, float(i) + 1.5),),
                timestamp=float(i) + 10.0,
            )
        )
    before = len(original.journal)
    original.checkpoint(checkpoint)
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert len(payload["journal"]) == before
    restored = PersistentStructuralHierarchy(checkpoint_path=checkpoint)
    assert len(restored.journal) == before


def test_snapshot_logger_rotation_after_persist(tmp_path: Path) -> None:
    log_path = tmp_path / "frames.ndjson"
    logger = SnapshotLogger(log_path, max_file_size_bytes=200)
    frame = ArchitecturePipeline(tick_size=TICK).evaluate(
        current_price=100.0,
        timestamp=1.0,
        candles=(),
        confirmed_highs=(),
        confirmed_lows=(),
    )
    assert isinstance(frame, ValidatorFrame)
    for _ in range(30):
        logger.log(frame)
    logger.close()

    previous = Path(str(log_path) + ".previous")
    assert log_path.exists()
    assert previous.exists()
    assert not Path(str(log_path) + ".previous.older").exists()
    assert previous.stat().st_size > 0
    for line in previous.read_text(encoding="utf-8").splitlines():
        if line.strip():
            json.loads(line)


def test_rotate_log_helper_deletes_older(tmp_path: Path) -> None:
    path = tmp_path / "x.ndjson"
    path.write_bytes(b"a" * 100)
    previous = Path(str(path) + ".previous")
    older = Path(str(path) + ".previous.older")
    previous.write_text("old\n", encoding="utf-8")
    older.write_text("older\n", encoding="utf-8")
    assert rotate_log_if_needed(path, max_bytes=50) is True
    assert path.exists()
    assert previous.exists()
    assert not older.exists()


def test_ndjson_refuses_without_proven_consumption(tmp_path: Path) -> None:
    path = tmp_path / "ticks.ndjson"
    path.write_text("{\"i\":1}\n{\"i\":2}\n", encoding="utf-8")
    assert enforce_ndjson_size_limit(path, max_bytes=1, consumed_offset=None) is False
    assert enforce_ndjson_size_limit(path, max_bytes=1, consumed_offset=0) is False
    assert path.read_text(encoding="utf-8").count("\n") == 2


def test_ndjson_drops_only_proven_consumed_prefix(tmp_path: Path) -> None:
    path = tmp_path / "ticks.ndjson"
    lines = [json.dumps({"i": i, "symbol": "MNQ"}) + "\n" for i in range(20)]
    path.write_text("".join(lines), encoding="utf-8")
    # Prove first 10 lines consumed (byte offset after those lines).
    consumed = len("".join(lines[:10]).encode("utf-8"))
    max_bytes = 10  # force retention attempt
    assert (
        enforce_ndjson_size_limit(path, max_bytes=max_bytes, consumed_offset=consumed)
        is True
    )
    kept = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert [row["i"] for row in kept] == list(range(10, 20))


def test_ingress_retention_does_not_redeliver(tmp_path: Path) -> None:
    path = tmp_path / "mnq_ticks.ndjson"
    path.write_text("", encoding="utf-8")
    ingress = LiveTickIngress(path)
    assert ingress.poll() == ()

    def _line(i: int) -> str:
        price = 20000.0 + i
        return json.dumps(
            {
                "timestamp": 1_700_000_000.0 + i,
                "symbol": "MNQ",
                "last_price": price,
                "bid": price - 0.25,
                "ask": price,
                "volume": 1.0,
            }
        )

    with path.open("a", encoding="utf-8") as handle:
        for i in range(10):
            handle.write(_line(i) + "\n")

    first = ingress.poll()
    assert len(first) == 10
    proven = ingress.proven_consumed_offset
    assert proven is not None and proven > 0

    # Force size limit so consumed prefix is dropped.
    assert ingress.apply_safe_storage_retention(max_bytes=1) is True
    # Remnant must not be re-delivered.
    assert ingress.poll() == ()

    with path.open("a", encoding="utf-8") as handle:
        handle.write(_line(99) + "\n")
    nxt = ingress.poll()
    assert len(nxt) == 1
    assert nxt[0].last_price == 20099.0


def test_audit_log_respects_configured_max(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reset_retention_config_for_tests()
    path = tmp_path / "ret.json"
    path.write_text(json.dumps({"audit_events_max_entries": 3}), encoding="utf-8")
    monkeypatch.setenv("HOTIRJAM_RETENTION_CONFIG", str(path))
    audit = AuditLog()
    assert audit.max_events == 3
    for i in range(10):
        audit.info(f"e{i}", timestamp=float(i))
    recent = audit.recent(10)
    assert len(recent) == 3
    assert recent[0].message == "e7"
    assert recent[-1].message == "e9"


def test_performance_page_shows_retention_block() -> None:
    snap = RetentionSnapshot(
        journal_entries=12,
        journal_limit=10_000,
        checkpoint_versions=12,
        version_limit=500,
        snapshot_log_size_bytes=2048,
        snapshot_log_limit_bytes=100 * 1024 * 1024,
        tick_file_size_bytes=4096,
        tick_file_limit_bytes=200 * 1024 * 1024,
        dom_file_size_bytes=None,
        dom_file_limit_bytes=200 * 1024 * 1024,
        retention_events=2,
    )
    text = render_performance_page(None, feed_status="LIVE", retention=snap)
    assert "RETENTION" in text
    assert "Current Journal Entries 12" in text
    assert "Journal Limit           10000" in text
    assert "Retention Events        2" in text
