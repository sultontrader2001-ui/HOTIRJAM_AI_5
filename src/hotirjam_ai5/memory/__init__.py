"""Market Memory Layer — passive observation history (Sprint 41+).

Does not influence Trade Decision. Append-only via adapters.
Sprint 43 adds read-only diagnostics (bands / consensus / timeline).
"""

from hotirjam_ai5.memory.diagnostics import (
    DIAG_FAST_SECONDS,
    DIAG_MEDIUM_SECONDS,
    DIAG_SLOW_SECONDS,
    TIMELINE_LIMIT,
    build_memory_diagnostics,
    build_timeline,
    compute_consensus,
    confidence_to_pct,
    items_in_band,
    normalize_direction,
    strength_to_pct,
    summarize_band,
    summarize_sources,
    summarize_store,
)
from hotirjam_ai5.memory.diagnostics_models import (
    BandSummary,
    ConsensusStatus,
    ConsensusSummary,
    MemoryBandName,
    MemoryDiagnosticsReport,
    SourceSummary,
    StoreDiagnosticsSummary,
    TimelineEvent,
)
from hotirjam_ai5.memory.memory_adapter import (
    BehaviorAdapter,
    DecisionAdapter,
    LiquidityAdapter,
    PhysicsAdapter,
    StateAdapter,
)
from hotirjam_ai5.memory.memory_snapshot import MemoryDiagnostics, MemorySnapshot
from hotirjam_ai5.memory.memory_store import (
    DEFAULT_MEMORY_CAPACITY,
    MarketMemoryStore,
)
from hotirjam_ai5.memory.memory_types import MemoryItem, MemorySource

__all__ = [
    "DEFAULT_MEMORY_CAPACITY",
    "DIAG_FAST_SECONDS",
    "DIAG_MEDIUM_SECONDS",
    "DIAG_SLOW_SECONDS",
    "TIMELINE_LIMIT",
    "BandSummary",
    "BehaviorAdapter",
    "ConsensusStatus",
    "ConsensusSummary",
    "DecisionAdapter",
    "LiquidityAdapter",
    "MarketMemoryStore",
    "MemoryBandName",
    "MemoryDiagnostics",
    "MemoryDiagnosticsReport",
    "MemoryItem",
    "MemorySnapshot",
    "MemorySource",
    "PhysicsAdapter",
    "SourceSummary",
    "StateAdapter",
    "StoreDiagnosticsSummary",
    "TimelineEvent",
    "build_memory_diagnostics",
    "build_timeline",
    "compute_consensus",
    "confidence_to_pct",
    "items_in_band",
    "normalize_direction",
    "strength_to_pct",
    "summarize_band",
    "summarize_sources",
    "summarize_store",
]
