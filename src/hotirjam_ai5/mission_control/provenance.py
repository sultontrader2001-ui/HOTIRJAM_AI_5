"""Provenance contract for Mission Control display fields (H-7.2).

Every UI field records where it came from. Presentation only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

NA = "N/A"
UNWIRED = "UNWIRED"
DISABLED = "DISABLED"


@dataclass(frozen=True, slots=True)
class ProvenancedField:
    """One display field with mandatory provenance."""

    value: str
    source_object: str
    source_field: str
    timestamp: float | None
    display_age: str

    def line(self, label: str, *, width: int = 14) -> str:
        """Single cockpit/lab line: label, value, source, age."""
        src = f"{self.source_object}.{self.source_field}"
        return (
            f"  {label.ljust(width)}  {self.value}  "
            f"| src={src}  | age={self.display_age}"
        )


def format_age(now: float, timestamp: float | None) -> str:
    """Presentation age string from existing timestamps only."""
    if timestamp is None:
        return NA
    age = now - timestamp
    if age < 0:
        age = 0.0
    if age < 1.0:
        return f"{age * 1000.0:.0f}ms"
    if age < 60.0:
        return f"{age:.1f}s"
    return f"{age / 60.0:.1f}m"


def fmt_value(value: Any, *, digits: int | None = 2) -> str:
    """Stringify an existing runtime value; None → N/A."""
    if value is None:
        return NA
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if digits is None:
            return str(value)
        return f"{value:.{digits}f}"
    if isinstance(value, (int, str)):
        text = str(value)
        return text if text else NA
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def unbound(
    *,
    reason: str = UNWIRED,
    source_object: str = "none",
    source_field: str = "none",
) -> ProvenancedField:
    """Explicit unbound field — never a fabricated market/AI value."""
    return ProvenancedField(
        value=reason,
        source_object=source_object,
        source_field=source_field,
        timestamp=None,
        display_age=NA,
    )


def bind(
    value: Any,
    *,
    source_object: str,
    source_field: str,
    timestamp: float | None,
    now: float,
    digits: int | None = 2,
    empty: str = NA,
) -> ProvenancedField:
    """Bind an existing runtime attribute into a provenanced field."""
    if value is None:
        return ProvenancedField(
            value=empty,
            source_object=source_object,
            source_field=source_field,
            timestamp=timestamp,
            display_age=format_age(now, timestamp),
        )
    text = fmt_value(value, digits=digits)
    if text == NA:
        text = empty
    return ProvenancedField(
        value=text,
        source_object=source_object,
        source_field=source_field,
        timestamp=timestamp,
        display_age=format_age(now, timestamp),
    )
