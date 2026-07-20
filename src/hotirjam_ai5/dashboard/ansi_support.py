"""Detect whether the terminal can interpret ANSI cursor sequences."""

from __future__ import annotations

import os
import sys
from typing import TextIO

_ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
_STD_OUTPUT_HANDLE = -11
_STD_ERROR_HANDLE = -12


def ansi_cursor_supported(stream: TextIO | None = None) -> bool:
    """Return True only when cursor ANSI sequences will be interpreted.

    Never assume stdout supports ANSI on Windows — PowerShell/cmd often print
    escapes as literal text unless Virtual Terminal Processing is enabled.
    """
    target = stream if stream is not None else sys.stdout
    forced = _forced_ansi_override()
    if forced is not None:
        return forced

    if not _is_tty(target):
        return False

    if os.name == "nt":
        return _windows_vt_enabled(target)

    term = os.environ.get("TERM", "")
    if term.lower() == "dumb":
        return False
    return True


def _forced_ansi_override() -> bool | None:
    raw = os.environ.get("HOTIRJAM_FORCE_ANSI", "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return None


def _is_tty(stream: TextIO) -> bool:
    isatty = getattr(stream, "isatty", None)
    return bool(isatty and isatty())


def _windows_vt_enabled(stream: TextIO) -> bool:
    """Enable and verify ENABLE_VIRTUAL_TERMINAL_PROCESSING on the console."""
    if stream is sys.stderr:
        handle_id = _STD_ERROR_HANDLE
    elif stream is sys.stdout:
        handle_id = _STD_OUTPUT_HANDLE
    else:
        # Custom streams are not the Windows console host.
        return False

    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return False

    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(handle_id)
        if handle in (0, -1):
            return False

        mode = wintypes.DWORD()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)) == 0:
            return False

        desired = mode.value | _ENABLE_VIRTUAL_TERMINAL_PROCESSING
        if desired != mode.value:
            if kernel32.SetConsoleMode(handle, desired) == 0:
                return False
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)) == 0:
                return False

        return bool(mode.value & _ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    except (AttributeError, OSError, ValueError):
        return False
