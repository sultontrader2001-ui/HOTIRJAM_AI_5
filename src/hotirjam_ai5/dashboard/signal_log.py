"""File-based signal log for observation-only internal activations.

Signal entries (BUY_INTERNAL / SELL_INTERNAL) must never appear on the
terminal dashboard. They are appended to a log file instead so the display
shows only current dashboard state.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_SIGNAL_LOG_PATH = Path("logs") / "signals.log"


class SignalLogWriter:
    """Appends one signal entry per line to a log file."""

    def __init__(self, path: Path | str = DEFAULT_SIGNAL_LOG_PATH) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def write(self, message: str) -> None:
        """Append one non-empty signal line to the log file."""
        text = message.strip()
        if not text:
            raise ValueError("signal log message must be non-empty")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(text + "\n")
