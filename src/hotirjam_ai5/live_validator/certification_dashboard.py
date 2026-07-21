"""Live Certification Dashboard — fixed-layout terminal UI (Sprint 1, UI only).

Presentation layer only:
- Reads existing snapshots from ``ValidatorFrame`` and feed telemetry.
- Performs no engine calls, no scoring, no new formulas.
- Every section is always rendered at the same position with the same
  line count; unavailable values are shown as ``N/A``.

Certification fields are placeholders (``N/A``) until real certification
statuses are wired in a later sprint. PASS/FAIL will occupy the same
fixed position.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone

from hotirjam_ai5.initiative import InitiativeSide
from hotirjam_ai5.live_validator.models import ValidatorFrame

_WIDTH = 32
_LABEL = 18
_RULE = "=" * _WIDTH
_SUB_RULE = "-" * _WIDTH
_NA = "N/A"
_RECENT_EVENT_LINES = 5

# Section keys accepted in the ``certifications`` mapping.
CERTIFICATION_KEYS = (
    "objective",
    "initiative",
    "response",
    "continuation",
    "break_capability",
)


@dataclass(frozen=True, slots=True)
class MarketTelemetry:
    """Feed-level display values captured by the app (presentation only)."""

    bid: float | None = None
    ask: float | None = None
    spread: float | None = None
    tick_rate: float | None = None
    latency_ms: float | None = None


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """One presentation-only dashboard event."""

    timestamp: float
    level: str  # INFO | WARNING | ERROR
    message: str


class AuditLog:
    """Presentation-only event collector for the AUDIT LOG section."""

    def __init__(self, *, max_events: int = 50) -> None:
        self._events: deque[AuditEvent] = deque(maxlen=max_events)
        self._counts = {"INFO": 0, "WARNING": 0, "ERROR": 0}

    def record(self, level: str, message: str, *, timestamp: float) -> None:
        level = level.upper()
        if level not in self._counts:
            level = "INFO"
        self._events.append(AuditEvent(timestamp=timestamp, level=level, message=message))
        self._counts[level] += 1

    def info(self, message: str, *, timestamp: float) -> None:
        self.record("INFO", message, timestamp=timestamp)

    def warning(self, message: str, *, timestamp: float) -> None:
        self.record("WARNING", message, timestamp=timestamp)

    def error(self, message: str, *, timestamp: float) -> None:
        self.record("ERROR", message, timestamp=timestamp)

    def count(self, level: str) -> int:
        return self._counts.get(level.upper(), 0)

    def recent(self, limit: int) -> tuple[AuditEvent, ...]:
        if limit <= 0:
            return ()
        return tuple(list(self._events)[-limit:])


def _field(label: str, value: str) -> str:
    return f"{label:<{_LABEL}}{value}"


def _fmt(value: float | None, *, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return _NA
    return f"{value:.{digits}f}{suffix}"


def _fmt_text(value: str | None) -> str:
    if value is None or value == "":
        return _NA
    return value


def _fmt_uptime(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return _NA
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _fmt_event_time(timestamp: float) -> str:
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%H:%M:%S")
    except (OverflowError, OSError, ValueError):
        return "--:--:--"


def _certification(certifications: Mapping[str, str] | None, key: str) -> str:
    """Fixed-position certification value: PASS, FAIL, or N/A."""
    if not certifications:
        return _NA
    value = certifications.get(key, "").upper()
    if value in {"PASS", "FAIL"}:
        return value
    return _NA


def _objective_state(frame: ValidatorFrame) -> str:
    obj = frame.objective
    if obj.is_complete:
        return "COMPLETE"
    if obj.has_high or obj.has_low:
        return "PARTIAL"
    return "NONE"


def _truncate(text: str, limit: int = 40) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def render_certification_dashboard(
    frame: ValidatorFrame,
    *,
    feed_status: str | None = None,
    market: MarketTelemetry | None = None,
    uptime_seconds: float | None = None,
    audit: AuditLog | None = None,
    certifications: Mapping[str, str] | None = None,
) -> str:
    """Render the fixed-layout Live Certification Dashboard."""
    mkt = market or MarketTelemetry()
    obj = frame.objective
    ini = frame.initiative
    resp = frame.response
    cont = frame.continuation
    brk = frame.break_capability
    feed = _fmt_text(feed_status)

    # Initiative pressures: existing initiative_score attributed to the
    # dominant side. No per-side pressure metric exists yet; the other
    # side is N/A. Relabel only — no computation.
    buyer_pressure: float | None = None
    seller_pressure: float | None = None
    if ini.initiative_side is InitiativeSide.BUYER:
        buyer_pressure = ini.initiative_score
    elif ini.initiative_side is InitiativeSide.SELLER:
        seller_pressure = ini.initiative_score

    lines = [
        _RULE,
        "HOTIRJAM AI 5",
        "LIVE CERTIFICATION DASHBOARD",
        _RULE,
        "MARKET",
        _SUB_RULE,
        _field("Symbol", _fmt_text(frame.symbol)),
        _field("Price", _fmt(frame.current_price)),
        _field("Bid", _fmt(mkt.bid)),
        _field("Ask", _fmt(mkt.ask)),
        _field("Spread", _fmt(mkt.spread)),
        _field("Tick Rate", _fmt(mkt.tick_rate, digits=1, suffix=" /s")),
        _field("Feed", feed),
        _field("Latency", _fmt(mkt.latency_ms, digits=0, suffix=" ms")),
        _RULE,
        "OBJECTIVE ENGINE",
        _SUB_RULE,
        _field("Current High", _fmt(obj.nearest_high_price)),
        _field("Current Low", _fmt(obj.nearest_low_price)),
        # Major High/Low: no certified structural source yet (Sprint 1 UI only).
        _field("Major High", _NA),
        _field("Major Low", _NA),
        _field("Distance High", _fmt(obj.nearest_high_distance_ticks, digits=1)),
        _field("Distance Low", _fmt(obj.nearest_low_distance_ticks, digits=1)),
        _field("Objective State", _objective_state(frame)),
        # ObjectiveSnapshot carries no confidence field.
        _field("Confidence", _NA),
        _field("Certification", _certification(certifications, "objective")),
        _RULE,
        "INITIATIVE ENGINE",
        _SUB_RULE,
        _field("Buyer Pressure", _fmt(buyer_pressure, digits=1)),
        _field("Seller Pressure", _fmt(seller_pressure, digits=1)),
        _field("Dominant Side", _fmt_text(ini.initiative_side.value)),
        _field("Confidence", _fmt(ini.confidence, digits=1)),
        _field("Reason", _truncate(_fmt_text(ini.reasons[0] if ini.reasons else None))),
        _field("Certification", _certification(certifications, "initiative")),
        _RULE,
        "RESPONSE ENGINE",
        _SUB_RULE,
        _field("Response Force", _fmt(resp.response_strength, digits=1)),
        # No absorption metric exists in ResponseSnapshot.
        _field("Absorption", _NA),
        _field("Reaction", _fmt_text(resp.response_state.value)),
        _field("Confidence", _fmt(resp.confidence, digits=1)),
        _field("Certification", _certification(certifications, "response")),
        _RULE,
        "CONTINUATION ENGINE",
        _SUB_RULE,
        _field("Continuation", _fmt(cont.continuation_score, digits=1)),
        _field("Weakening", _fmt(cont.momentum_decay, digits=1)),
        # No exhaustion metric exists in ContinuationSnapshot.
        _field("Exhaustion", _NA),
        _field("Confidence", _fmt(cont.confidence, digits=1)),
        _field("Certification", _certification(certifications, "continuation")),
        _RULE,
        "BREAK CAPABILITY",
        _SUB_RULE,
        _field("Break Probability", _fmt(brk.break_probability, digits=1)),
        _field("Target", _fmt_text(brk.target_type.value)),
        _field("Pressure", _fmt(brk.pressure_score, digits=1)),
        _field("Confidence", _fmt(brk.confidence, digits=1)),
        _field("Certification", _certification(certifications, "break_capability")),
        _RULE,
        "SYSTEM",
        _SUB_RULE,
        _field("Decision", _fmt_text(frame.decision)),
        _field("Execution", "DISABLED"),
        _field("Feed", feed),
        _field("Uptime", _fmt_uptime(uptime_seconds)),
        _RULE,
        "AUDIT LOG",
        _SUB_RULE,
        _field("INFO", str(audit.count("INFO")) if audit else _NA),
        _field("WARNING", str(audit.count("WARNING")) if audit else _NA),
        _field("ERROR", str(audit.count("ERROR")) if audit else _NA),
        "Recent Events",
    ]

    events = audit.recent(_RECENT_EVENT_LINES) if audit else ()
    for event in events:
        line = f"  {_fmt_event_time(event.timestamp)} {event.level:<7} {event.message}"
        lines.append(_truncate(line, limit=60))
    for _ in range(_RECENT_EVENT_LINES - len(events)):
        lines.append(f"  {_NA}")

    lines.extend(
        [
            _RULE,
            "Press D — Developer View",
        ]
    )
    return "\n".join(lines)
