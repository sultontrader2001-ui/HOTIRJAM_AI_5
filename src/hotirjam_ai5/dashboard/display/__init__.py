"""Display adapters for the TerminalDisplay facade (H-7.2C)."""

from hotirjam_ai5.dashboard.display.adapter import DisplayAdapter, Viewport
from hotirjam_ai5.dashboard.display.ansi_cursor import AnsiCursorAdapter
from hotirjam_ai5.dashboard.display.capture import CaptureAdapter
from hotirjam_ai5.dashboard.display.compatible_home import CompatibleHomeAdapter

__all__ = [
    "AnsiCursorAdapter",
    "CaptureAdapter",
    "CompatibleHomeAdapter",
    "DisplayAdapter",
    "Viewport",
]
