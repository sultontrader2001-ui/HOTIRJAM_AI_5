"""H-6.7 bounded retention — config, file rotation, and diagnostics."""

from __future__ import annotations

from hotirjam_ai5.retention.config import (
    RetentionConfig,
    default_retention_config_path,
    load_retention_config,
    reset_retention_config_for_tests,
)
from hotirjam_ai5.retention.files import (
    enforce_ndjson_size_limit,
    rotate_log_if_needed,
)
from hotirjam_ai5.retention.stats import (
    RetentionSnapshot,
    RetentionStats,
    get_retention_stats,
    record_retention_event,
    reset_retention_stats_for_tests,
)

__all__ = [
    "RetentionConfig",
    "RetentionSnapshot",
    "RetentionStats",
    "default_retention_config_path",
    "enforce_ndjson_size_limit",
    "get_retention_stats",
    "load_retention_config",
    "record_retention_event",
    "reset_retention_config_for_tests",
    "reset_retention_stats_for_tests",
    "rotate_log_if_needed",
]
