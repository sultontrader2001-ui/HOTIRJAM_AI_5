"""Live Validator — observation-only architecture pipeline on the live stream.

Decision Engine: DISABLED
Execution Engine: DISABLED
"""

from hotirjam_ai5.live_validator.app import LiveValidatorApp, main
from hotirjam_ai5.live_validator.candle_builder import TickBarBuilder
from hotirjam_ai5.live_validator.certification_dashboard import (
    AuditLog,
    MarketTelemetry,
    render_certification_dashboard,
)
from hotirjam_ai5.live_validator.controller import LiveValidatorController
from hotirjam_ai5.live_validator.display import render_validator_frame
from hotirjam_ai5.live_validator.idc import render_idc, render_idc_main_menu
from hotirjam_ai5.live_validator.logger import SnapshotLogger
from hotirjam_ai5.live_validator.loop_timing import (
    LoopTimingSnapshot,
    StageBreakdown,
    TimingSeverity,
)
from hotirjam_ai5.live_validator.models import ValidatorFrame
from hotirjam_ai5.live_validator.pipeline import ArchitecturePipeline
from hotirjam_ai5.live_validator.presentation_mode import IdcPage, PresentationMode
from hotirjam_ai5.live_validator.swing_confirmer import SwingConfirmer

__all__ = [
    "ArchitecturePipeline",
    "AuditLog",
    "IdcPage",
    "LiveValidatorApp",
    "LiveValidatorController",
    "LoopTimingSnapshot",
    "MarketTelemetry",
    "PresentationMode",
    "SnapshotLogger",
    "StageBreakdown",
    "SwingConfirmer",
    "TickBarBuilder",
    "TimingSeverity",
    "ValidatorFrame",
    "main",
    "render_certification_dashboard",
    "render_idc",
    "render_idc_main_menu",
    "render_validator_frame",
]
