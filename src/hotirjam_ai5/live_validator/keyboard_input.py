"""Cross-platform non-blocking keyboard input for the Live Validator UI.

Presentation layer only. POSIX uses termios/tty + select; Windows uses
msvcrt. Neither module is imported on the other platform.
"""

from __future__ import annotations

import sys

_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:
    import msvcrt
else:
    import select
    import termios
    import tty


class KeyboardInput:
    """Non-blocking single-key reader with terminal-mode save/restore."""

    def __init__(self) -> None:
        self._old_term: list | None = None

    def enable(self) -> None:
        """Switch stdin to unbuffered key mode (POSIX only; no-op on Windows)."""
        if _IS_WINDOWS:
            return
        if not sys.stdin.isatty():
            return
        try:
            self._old_term = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        except (termios.error, OSError):
            self._old_term = None

    def disable(self) -> None:
        """Restore the original terminal mode (POSIX only; no-op on Windows)."""
        if _IS_WINDOWS:
            return
        if self._old_term is None:
            return
        try:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_term)
        except (termios.error, OSError):
            pass
        self._old_term = None

    def poll_key(self) -> str | None:
        """Return one pending key press without blocking, or None."""
        if _IS_WINDOWS:
            try:
                if msvcrt.kbhit():
                    return msvcrt.getwch()
            except OSError:
                return None
            return None

        if not sys.stdin.isatty():
            return None
        try:
            ready, _, _ = select.select([sys.stdin], [], [], 0)
        except (OSError, ValueError):
            return None
        if not ready:
            return None
        try:
            return sys.stdin.read(1)
        except OSError:
            return None
