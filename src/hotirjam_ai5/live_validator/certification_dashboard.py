"""Live Certification Dashboard V2 — two-column trading terminal UI.

Presentation layer only:
- Reads existing snapshots from ``ValidatorFrame`` and feed telemetry.
- Performs no engine calls, no scoring, no new formulas.
- Fixed two-column layout; panels never move or change order.
- Unavailable values are shown as ``N/A``.

Certification badges are placeholders (``N/A``) until real certification
statuses are wired in a later sprint. PASS/FAIL occupy a fixed title slot.
"""

from __future__ import annotations

import re
import shutil
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from hotirjam_ai5.live_validator.models import ValidatorFrame

_NA = "N/A"
_MIN_WIDTH = 72
_DEFAULT_WIDTH = 100
_LABEL = 14
_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

CERTIFICATION_KEYS = (
    "objective",
    "initiative",
    "response",
    "continuation",
    "break_capability",
)

_RESET = "\033[0m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_GRAY = "\033[90m"


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


def _visible_len(text: str) -> int:
    return len(_ANSI_RE.sub("", text))


def _pad(text: str, width: int) -> str:
    """Pad or truncate to ``width`` visible columns (ANSI-safe)."""
    visible = _visible_len(text)
    if visible > width:
        plain = _ANSI_RE.sub("", text)
        if width <= 1:
            return plain[:width]
        return plain[: width - 1] + "…"
    return text + (" " * (width - visible))


def _colorize(text: str, code: str, *, enabled: bool) -> str:
    if not enabled or text == "":
        return text
    return f"{code}{text}{_RESET}"


def _style_status(value: str, *, use_color: bool) -> str:
    """Color PASS / FAIL / WARNING / ERROR / N/A / STALE when supported."""
    upper = value.upper()
    if upper in {"PASS", "LOCKED", "LIVE"}:
        return _colorize(value, _GREEN, enabled=use_color)
    if upper in {"FAIL", "ERROR"}:
        return _colorize(value, _RED, enabled=use_color)
    if upper in {"WARNING", "STALE", "TESTING"}:
        return _colorize(value, _YELLOW, enabled=use_color)
    if upper in {_NA, "NOT TESTED", "NOT IMPLEMENTED"}:
        return _colorize(value, _GRAY, enabled=use_color)
    return value


def _fmt(value: float | None, *, digits: int = 2, suffix: str = "", use_color: bool = False) -> str:
    if value is None:
        return _style_status(_NA, use_color=use_color)
    return f"{value:.{digits}f}{suffix}"


def _fmt_text(value: str | None, *, use_color: bool = False) -> str:
    if value is None or value == "":
        return _style_status(_NA, use_color=use_color)
    return value


def _fmt_uptime(seconds: float | None, *, use_color: bool = False) -> str:
    if seconds is None or seconds < 0:
        return _style_status(_NA, use_color=use_color)
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _fmt_event_time(timestamp: float) -> str:
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%H:%M:%S")
    except (OverflowError, OSError, ValueError):
        return "--:--:--"


_OBJECTIVE_CERT_VALUES = frozenset({"NOT TESTED", "TESTING", "PASS", "LOCKED"})
_OBJECTIVE_LABEL = 21  # one pad past "Structural Objective" (20)


def _certification(certifications: Mapping[str, str] | None, key: str) -> str:
    if not certifications:
        return _NA
    value = certifications.get(key, "").upper()
    if value in {"PASS", "FAIL"}:
        return value
    return _NA


def _objective_certification(certifications: Mapping[str, str] | None) -> str:
    """Objective panel certification: NOT TESTED | TESTING | PASS | LOCKED only."""
    if not certifications:
        return "NOT TESTED"
    raw = certifications.get("objective", "")
    value = str(raw).upper().replace("_", " ").strip()
    if value in _OBJECTIVE_CERT_VALUES:
        return value
    return "NOT TESTED"


def _objective_state(frame: ValidatorFrame) -> str:
    obj = frame.objective
    if obj.is_complete:
        return "READY"
    if obj.has_high or obj.has_low:
        return "PARTIAL"
    return "NONE"


def _distance_summary(frame: ValidatorFrame, *, use_color: bool) -> str:
    """Compact Distance field (keeps panel height when Current High/Low are split)."""
    obj = frame.objective
    high = obj.nearest_high_distance_ticks
    low = obj.nearest_low_distance_ticks
    if high is None and low is None:
        return _style_status(_NA, use_color=use_color)
    return f"H {_fmt(high, digits=1, use_color=use_color)}  L {_fmt(low, digits=1, use_color=use_color)}"


def _resolve_width(terminal_width: int | None) -> int:
    if terminal_width is not None and terminal_width >= _MIN_WIDTH:
        width = terminal_width
    else:
        try:
            width = shutil.get_terminal_size(fallback=(_DEFAULT_WIDTH, 24)).columns
        except OSError:
            width = _DEFAULT_WIDTH
        width = max(_MIN_WIDTH, width)
    # Dual panel: |panel|panel| → width = 2*panel + 3.
    # Grow (not shrink) so we use the full console when width is off-by-one.
    if (width - 3) % 2 != 0:
        width += 1
    return max(width, _MIN_WIDTH if (_MIN_WIDTH - 3) % 2 == 0 else _MIN_WIDTH + 1)


def _field(label: str, value: str, *, inner: int, label_width: int = _LABEL) -> str:
    label_part = f"{label:<{label_width}}"
    remaining = max(1, inner - label_width)
    return label_part + _pad(value, remaining)


def _panel(
    title: str,
    fields: Sequence[tuple[str, str]],
    *,
    inner: int,
    badge: str | None = None,
    use_color: bool = False,
    label_width: int = _LABEL,
) -> list[str]:
    """Title, underline, then field rows. Height normalized later."""
    if badge is not None:
        badge_s = _style_status(badge, use_color=use_color)
        gap = max(1, inner - _visible_len(title) - _visible_len(badge_s))
        header = _pad(f"{title}{' ' * gap}{badge_s}", inner)
    else:
        header = _pad(title, inner)
    lines = [header, _pad("-" * min(inner, max(8, _visible_len(title) + 2)), inner)]
    for label, value in fields:
        lines.append(_field(label, value, inner=inner, label_width=label_width))
    return lines


def _equalize(panels: Sequence[list[str]], *, inner: int) -> list[list[str]]:
    height = max(len(p) for p in panels)
    out: list[list[str]] = []
    for panel in panels:
        padded = list(panel)
        while len(padded) < height:
            padded.append(_pad("", inner))
        out.append(padded)
    return out


def _box_row(left: Sequence[str], right: Sequence[str], *, panel: int) -> list[str]:
    return [f"|{_pad(l, panel)}|{_pad(r, panel)}|" for l, r in zip(left, right, strict=True)]


def _full_bar(width: int) -> str:
    return "+" + ("-" * (width - 2)) + "+"


def _dual_bar(panel: int) -> str:
    return "+" + ("-" * panel) + "+" + ("-" * panel) + "+"


def render_certification_dashboard(
    frame: ValidatorFrame,
    *,
    feed_status: str | None = None,
    market: MarketTelemetry | None = None,
    uptime_seconds: float | None = None,
    audit: AuditLog | None = None,
    certifications: Mapping[str, str] | None = None,
    terminal_width: int | None = None,
    use_color: bool = False,
) -> str:
    """Render the fixed two-column Live Certification Dashboard."""
    width = _resolve_width(terminal_width)
    panel_w = (width - 3) // 2
    inner = panel_w
    inner_full = width - 2

    mkt = market or MarketTelemetry()
    obj = frame.objective
    ini = frame.initiative
    resp = frame.response
    cont = frame.continuation
    brk = frame.break_capability

    feed_raw = feed_status if feed_status else _NA
    feed_styled = _style_status(feed_raw, use_color=use_color)
    runtime = _fmt_uptime(uptime_seconds, use_color=use_color)
    session = _fmt_text(frame.symbol, use_color=use_color)

    buyer = ini.buyer_initiative if ini.buyer_initiative > 0.0 else None
    seller = ini.seller_initiative if ini.seller_initiative > 0.0 else None

    market_panel = _panel(
        "MARKET",
        [
            ("Price", _fmt(frame.current_price, use_color=use_color)),
            ("Bid", _fmt(mkt.bid, use_color=use_color)),
            ("Ask", _fmt(mkt.ask, use_color=use_color)),
            ("Spread", _fmt(mkt.spread, use_color=use_color)),
            ("Tick Rate", _fmt(mkt.tick_rate, digits=1, suffix=" /s", use_color=use_color)),
            ("Latency", _fmt(mkt.latency_ms, digits=0, suffix=" ms", use_color=use_color)),
        ],
        inner=inner,
        use_color=use_color,
    )
    # Current Objective = Current High / Current Low (separate rows).
    # Distance stays as one compact row so panel height matches MARKET (6 fields).
    # Structural Objective is not built yet — show NOT IMPLEMENTED (never N/A).
    objective_panel = _panel(
        "OBJECTIVE ENGINE",
        [
            ("Current High", _fmt(obj.nearest_high_price, use_color=use_color)),
            ("Current Low", _fmt(obj.nearest_low_price, use_color=use_color)),
            ("Distance", _distance_summary(frame, use_color=use_color)),
            (
                "Structural Objective",
                _style_status("NOT IMPLEMENTED", use_color=use_color),
            ),
            ("Calculation State", _objective_state(frame)),
            (
                "Certification",
                _style_status(_objective_certification(certifications), use_color=use_color),
            ),
        ],
        inner=inner,
        use_color=use_color,
        label_width=_OBJECTIVE_LABEL,
    )
    initiative_panel = _panel(
        "INITIATIVE ENGINE",
        [
            ("Buyer", _fmt(buyer, digits=1, use_color=use_color)),
            ("Seller", _fmt(seller, digits=1, use_color=use_color)),
            ("Dominant Side", _fmt_text(ini.dominant_side.value, use_color=use_color)),
            ("Confidence", _fmt(ini.confidence, digits=1, use_color=use_color)),
        ],
        inner=inner,
        badge=_certification(certifications, "initiative"),
        use_color=use_color,
    )
    response_panel = _panel(
        "RESPONSE ENGINE",
        [
            ("Reaction", _fmt_text(resp.response_state.value, use_color=use_color)),
            ("Force", _fmt(resp.response_strength, digits=1, use_color=use_color)),
            ("Confidence", _fmt(resp.confidence, digits=1, use_color=use_color)),
        ],
        inner=inner,
        badge=_certification(certifications, "response"),
        use_color=use_color,
    )
    continuation_panel = _panel(
        "CONTINUATION ENGINE",
        [
            ("Continuation", _fmt(cont.continuation_score, digits=1, use_color=use_color)),
            ("Weakening", _fmt(cont.momentum_decay, digits=1, use_color=use_color)),
            ("Confidence", _fmt(cont.confidence, digits=1, use_color=use_color)),
        ],
        inner=inner,
        badge=_certification(certifications, "continuation"),
        use_color=use_color,
    )
    break_panel = _panel(
        "BREAK CAPABILITY",
        [
            ("Target", _fmt_text(brk.target_type.value, use_color=use_color)),
            ("Break Prob", _fmt(brk.break_probability, digits=1, use_color=use_color)),
            ("Pressure", _fmt(brk.pressure_score, digits=1, use_color=use_color)),
        ],
        inner=inner,
        badge=_certification(certifications, "break_capability"),
        use_color=use_color,
    )
    system_panel = _panel(
        "SYSTEM",
        [
            ("Decision", _fmt_text(frame.decision, use_color=use_color)),
            ("Execution", "DISABLED"),
            ("Feed", feed_styled),
            ("Uptime", runtime),
        ],
        inner=inner,
        use_color=use_color,
    )

    if audit is None:
        info_s = _style_status(_NA, use_color=use_color)
        warn_s = _style_status(_NA, use_color=use_color)
        err_s = _style_status(_NA, use_color=use_color)
        recent_s = _style_status(_NA, use_color=use_color)
    else:
        info_s = str(audit.count("INFO"))
        warn_n = audit.count("WARNING")
        err_n = audit.count("ERROR")
        warn_s = _style_status(str(warn_n), use_color=use_color) if warn_n > 0 else str(warn_n)
        err_s = _colorize(str(err_n), _RED, enabled=use_color) if err_n > 0 else str(err_n)
        recent = audit.recent(1)
        if recent:
            ev = recent[0]
            recent_s = (
                f"{_fmt_event_time(ev.timestamp)} "
                f"{_style_status(ev.level, use_color=use_color)} {ev.message}"
            )
        else:
            recent_s = _style_status(_NA, use_color=use_color)

    audit_panel = _panel(
        "AUDIT LOG",
        [
            ("INFO", info_s),
            ("WARNING", warn_s),
            ("ERROR", err_s),
            ("Recent Event", recent_s),
        ],
        inner=inner,
        use_color=use_color,
    )

    market_panel, objective_panel = _equalize((market_panel, objective_panel), inner=inner)
    initiative_panel, response_panel = _equalize(
        (initiative_panel, response_panel), inner=inner
    )
    continuation_panel, break_panel = _equalize(
        (continuation_panel, break_panel), inner=inner
    )
    system_panel, audit_panel = _equalize((system_panel, audit_panel), inner=inner)

    full = _full_bar(width)
    dual = _dual_bar(panel_w)
    meta = f"Runtime {runtime}   Session {session}   Feed {feed_styled}"

    lines: list[str] = [
        full,
        f"|{_pad('HOTIRJAM AI 5', inner_full)}|",
        f"|{_pad('LIVE CERTIFICATION DASHBOARD', inner_full)}|",
        f"|{_pad(meta, inner_full)}|",
        dual,
    ]
    lines.extend(_box_row(market_panel, objective_panel, panel=panel_w))
    lines.append(dual)
    lines.extend(_box_row(initiative_panel, response_panel, panel=panel_w))
    lines.append(dual)
    lines.extend(_box_row(continuation_panel, break_panel, panel=panel_w))
    lines.append(dual)
    lines.extend(_box_row(system_panel, audit_panel, panel=panel_w))
    lines.append(full)
    lines.append(f"|{_pad('Press D - Developer View', inner_full)}|")
    lines.append(full)
    return "\n".join(lines)
