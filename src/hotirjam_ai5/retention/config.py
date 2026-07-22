"""Load retention limits from JSON (no code change required to tune)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

_ENV_CONFIG = "HOTIRJAM_RETENTION_CONFIG"

_DEFAULTS = {
    "objective_journal_max_entries": 10_000,
    "hierarchy_max_versions": 500,
    "snapshot_log_max_file_size_mb": 100,
    "tick_ndjson_max_file_size_mb": 200,
    "dom_ndjson_max_file_size_mb": 200,
    "audit_events_max_entries": 50_000,
}

_cached: RetentionConfig | None = None


@dataclass(frozen=True, slots=True)
class RetentionConfig:
    """Upper bounds for runtime history. Loaded from retention.json."""

    objective_journal_max_entries: int = 10_000
    hierarchy_max_versions: int = 500
    snapshot_log_max_file_size_mb: int = 100
    tick_ndjson_max_file_size_mb: int = 200
    dom_ndjson_max_file_size_mb: int = 200
    audit_events_max_entries: int = 50_000

    @property
    def snapshot_log_max_bytes(self) -> int:
        return int(self.snapshot_log_max_file_size_mb) * 1024 * 1024

    @property
    def tick_ndjson_max_bytes(self) -> int:
        return int(self.tick_ndjson_max_file_size_mb) * 1024 * 1024

    @property
    def dom_ndjson_max_bytes(self) -> int:
        return int(self.dom_ndjson_max_file_size_mb) * 1024 * 1024

    @property
    def hierarchy_journal_cap(self) -> int:
        """Effective in-memory/checkpoint journal cap (newest entries only)."""
        return min(
            max(1, int(self.objective_journal_max_entries)),
            max(1, int(self.hierarchy_max_versions)),
        )


def default_retention_config_path() -> Path:
    """Canonical project config: ``<repo>/config/retention.json``."""
    # src/hotirjam_ai5/retention/config.py → parents[3] = HOTIRJAM_AI_5
    return Path(__file__).resolve().parents[3] / "config" / "retention.json"


def _coerce_int(raw: object, default: int, *, name: str) -> int:
    try:
        value = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"retention.{name} must be an integer") from exc
    if value < 1:
        raise ValueError(f"retention.{name} must be >= 1")
    return value


def _from_mapping(data: dict[str, object]) -> RetentionConfig:
    merged = dict(_DEFAULTS)
    merged.update({k: v for k, v in data.items() if k in _DEFAULTS})
    return RetentionConfig(
        objective_journal_max_entries=_coerce_int(
            merged["objective_journal_max_entries"],
            _DEFAULTS["objective_journal_max_entries"],
            name="objective_journal_max_entries",
        ),
        hierarchy_max_versions=_coerce_int(
            merged["hierarchy_max_versions"],
            _DEFAULTS["hierarchy_max_versions"],
            name="hierarchy_max_versions",
        ),
        snapshot_log_max_file_size_mb=_coerce_int(
            merged["snapshot_log_max_file_size_mb"],
            _DEFAULTS["snapshot_log_max_file_size_mb"],
            name="snapshot_log_max_file_size_mb",
        ),
        tick_ndjson_max_file_size_mb=_coerce_int(
            merged["tick_ndjson_max_file_size_mb"],
            _DEFAULTS["tick_ndjson_max_file_size_mb"],
            name="tick_ndjson_max_file_size_mb",
        ),
        dom_ndjson_max_file_size_mb=_coerce_int(
            merged["dom_ndjson_max_file_size_mb"],
            _DEFAULTS["dom_ndjson_max_file_size_mb"],
            name="dom_ndjson_max_file_size_mb",
        ),
        audit_events_max_entries=_coerce_int(
            merged["audit_events_max_entries"],
            _DEFAULTS["audit_events_max_entries"],
            name="audit_events_max_entries",
        ),
    )


def load_retention_config(path: str | Path | None = None) -> RetentionConfig:
    """Load retention limits (cached). Missing file → built-in defaults."""
    global _cached
    if path is None and _cached is not None:
        return _cached

    candidates: list[Path] = []
    if path is not None:
        candidates.append(Path(path))
    else:
        env = os.environ.get(_ENV_CONFIG, "").strip()
        if env:
            candidates.append(Path(env).expanduser())
        candidates.append(Path.cwd() / "config" / "retention.json")
        candidates.append(default_retention_config_path())

    for candidate in candidates:
        try:
            if candidate.is_file():
                payload = json.loads(candidate.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("retention config must be a JSON object")
                cfg = _from_mapping(payload)
                if path is None:
                    _cached = cfg
                return cfg
        except OSError:
            continue

    cfg = _from_mapping({})
    if path is None:
        _cached = cfg
    return cfg


def reset_retention_config_for_tests() -> None:
    """Clear cached config (tests only)."""
    global _cached
    _cached = None
