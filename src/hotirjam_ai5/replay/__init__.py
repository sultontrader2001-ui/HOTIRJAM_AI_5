"""H-8.1 Replay Validation layer.

Read-only consumer of H-8.0 ObservationCycle records + subsequent market points.
Never mutates observations, RuntimeHub, AI, or Decision. Never sends orders.
"""

from hotirjam_ai5.replay.engine import ReplayValidator
from hotirjam_ai5.replay.models import (
    ConfidenceLabel,
    MarketPoint,
    ModuleVerdict,
    ObservationReplayResult,
    ReplayReport,
)
from hotirjam_ai5.replay.report import format_replay_report

__all__ = [
    "ConfidenceLabel",
    "MarketPoint",
    "ModuleVerdict",
    "ObservationReplayResult",
    "ReplayReport",
    "ReplayValidator",
    "format_replay_report",
    "main",
]


def __getattr__(name: str):
    if name == "main":
        from hotirjam_ai5.replay.app import main as _main

        return _main
    raise AttributeError(name)
