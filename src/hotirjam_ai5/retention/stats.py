"""Retention event counters and Performance-page snapshot.

No locks on the hot path — counters use plain integers (CPython GIL).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hotirjam_ai5.retention.config import RetentionConfig, load_retention_config

_event_count = 0


@dataclass(frozen=True, slots=True)
class RetentionSnapshot:
    """Read-only retention diagnostics for the Performance page."""

    journal_entries: int
    journal_limit: int
    checkpoint_versions: int
    version_limit: int
    snapshot_log_size_bytes: int | None
    snapshot_log_limit_bytes: int
    tick_file_size_bytes: int | None
    tick_file_limit_bytes: int
    dom_file_size_bytes: int | None
    dom_file_limit_bytes: int
    retention_events: int


@dataclass
class RetentionStats:
    """Mutable binder for live paths used by diagnostics."""

    config: RetentionConfig
    journal_entries: int = 0
    hierarchy_version: int = 0
    snapshot_log_path: Path | None = None
    tick_path: Path | None = None
    dom_path: Path | None = None

    def snapshot(self) -> RetentionSnapshot:
        return RetentionSnapshot(
            journal_entries=self.journal_entries,
            journal_limit=self.config.objective_journal_max_entries,
            checkpoint_versions=self.hierarchy_version,
            version_limit=self.config.hierarchy_max_versions,
            snapshot_log_size_bytes=_safe_size(self.snapshot_log_path),
            snapshot_log_limit_bytes=self.config.snapshot_log_max_bytes,
            tick_file_size_bytes=_safe_size(self.tick_path),
            tick_file_limit_bytes=self.config.tick_ndjson_max_bytes,
            dom_file_size_bytes=_safe_size(self.dom_path),
            dom_file_limit_bytes=self.config.dom_ndjson_max_bytes,
            retention_events=get_retention_event_count(),
        )


_stats: RetentionStats | None = None


def _safe_size(path: Path | None) -> int | None:
    if path is None:
        return None
    try:
        if path.is_file():
            return path.stat().st_size
    except OSError:
        return None
    return None


def get_retention_stats() -> RetentionStats:
    global _stats
    if _stats is None:
        _stats = RetentionStats(config=load_retention_config())
    return _stats


def record_retention_event() -> None:
    global _event_count
    _event_count += 1


def get_retention_event_count() -> int:
    return _event_count


def reset_retention_stats_for_tests() -> None:
    global _stats, _event_count
    _event_count = 0
    _stats = None
