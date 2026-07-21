"""Presentation-mode state for the Live Validator UI.

Presentation layer only. Does not touch engines, frames, or checkpoints.
Developer View remains an independent overlay on the Dashboard mode.
"""

from __future__ import annotations

from enum import StrEnum


class PresentationMode(StrEnum):
    """Top-level UI mode. Rendering only — shared runtime underneath."""

    DASHBOARD = "DASHBOARD"
    IDC = "IDC"


class IdcPage(StrEnum):
    """IDC navigation target. Framework pages only in H-6.6.1."""

    MENU = "MENU"
    OBJECTIVE = "OBJECTIVE"
    INITIATIVE = "INITIATIVE"
    RESPONSE = "RESPONSE"
    CONTINUATION = "CONTINUATION"
    BREAK_CAPABILITY = "BREAK_CAPABILITY"
    MARKET_STATE = "MARKET_STATE"
    PHYSICS = "PHYSICS"
    STRUCTURAL_MEMORY = "STRUCTURAL_MEMORY"
    PERFORMANCE = "PERFORMANCE"
    LIVE_AUDIT = "LIVE_AUDIT"
    CERTIFICATION = "CERTIFICATION"
    WARNINGS = "WARNINGS"
