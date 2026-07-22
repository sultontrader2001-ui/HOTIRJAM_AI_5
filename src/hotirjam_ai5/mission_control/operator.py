"""H-7.3 Professional Operator UX — fixed three-column layout.

Presentation only. Uses certified Terminal Display via callers.
Never evaluates engines. Never scrolls: clamps to viewport height.
"""

from __future__ import annotations

from hotirjam_ai5.mission_control.bind_operator import bind_operator_regions
from hotirjam_ai5.mission_control.provenance import ProvenancedField
from hotirjam_ai5.mission_control.render_format import (
    clamp_lines,
    dedupe_consecutive,
    fit_line,
    format_age_display,
    short_source,
    terminal_height,
    terminal_width,
    truncate,
)
from hotirjam_ai5.mission_control.runtime_bundle import RuntimeBundle

_HEADER_ROWS = 5
_BOTTOM_ROWS = 5
_MIN_BODY_ROWS = 10
_GAP = " │ "


def render_operator(
    bundle: RuntimeBundle | None = None,
    *,
    width: int | None = None,
    height: int | None = None,
    focus: str | None = None,
) -> str:
    """Render HEADER + LEFT/CENTER/RIGHT + BOTTOM in one fixed viewport frame."""
    if bundle is None:
        import time

        bundle = RuntimeBundle(now=time.time())

    panel_width = max(40, int(width) if width is not None else terminal_width())
    view_height = max(20, int(height) if height is not None else terminal_height())
    regions = bind_operator_regions(bundle)

    header = _render_header(regions["header"], width=panel_width, now=bundle.now, focus=focus)
    bottom = _render_bottom(regions["bottom"], width=panel_width, now=bundle.now)
    body_budget = max(
        _MIN_BODY_ROWS,
        view_height - len(header) - len(bottom),
    )

    if panel_width < 90:
        body = _render_stacked(
            regions,
            width=panel_width,
            rows=body_budget,
            now=bundle.now,
            focus=focus,
        )
    else:
        col_w = max(18, (panel_width - 2 * len(_GAP)) // 3)
        rem = panel_width - (col_w * 3 + 2 * len(_GAP))
        left_w, center_w, right_w = col_w, col_w + rem, col_w

        left = _panel_block(
            "TRADING COCKPIT",
            regions["left"],
            width=left_w,
            rows=body_budget,
            now=bundle.now,
            focused=focus == "left",
        )
        center = _panel_block(
            "AI LABORATORY",
            regions["center"],
            width=center_w,
            rows=body_budget,
            now=bundle.now,
            focused=focus == "center",
        )
        right = _panel_block(
            "DEVELOPER",
            regions["right"],
            width=right_w,
            rows=body_budget,
            now=bundle.now,
            focused=focus == "right",
        )
        body = [
            fit_line(f"{left[i]}{_GAP}{center[i]}{_GAP}{right[i]}", panel_width)
            for i in range(body_budget)
        ]

    lines = header + body + bottom
    lines = dedupe_consecutive(clamp_lines(lines, panel_width))
    if len(lines) > view_height:
        lines = lines[:view_height]
    return "\n".join(lines)


def _render_stacked(
    regions: dict[str, dict[str, ProvenancedField]],
    *,
    width: int,
    rows: int,
    now: float,
    focus: str | None,
) -> list[str]:
    """Narrow terminals: stack panels without horizontal overflow."""
    chunks = [
        _panel_block(
            "TRADING COCKPIT",
            regions["left"],
            width=width,
            rows=max(4, rows // 3),
            now=now,
            focused=focus == "left",
        ),
        _panel_block(
            "AI LABORATORY",
            regions["center"],
            width=width,
            rows=max(4, rows // 3),
            now=now,
            focused=focus == "center",
        ),
        _panel_block(
            "DEVELOPER",
            regions["right"],
            width=width,
            rows=max(4, rows - 2 * (rows // 3)),
            now=now,
            focused=focus == "right",
        ),
    ]
    out: list[str] = []
    for chunk in chunks:
        out.extend(chunk)
    if len(out) < rows:
        out.extend(" " * width for _ in range(rows - len(out)))
    return [fit_line(line, width) for line in out[:rows]]


def _render_header(
    fields: dict[str, ProvenancedField],
    *,
    width: int,
    now: float,
    focus: str | None,
) -> list[str]:
    product = fields["Product"].value
    symbol = fields["Symbol"].value
    last = fields["Last"].value
    session = fields["Session"].value
    market = fields["Market State"].value
    ai = fields["AI Status"].value
    health = fields["System Health"].value
    decision = fields["Decision"].value
    execution = fields["Execution"].value
    focus_tag = {
        "left": "FOCUS:COCKPIT",
        "center": "FOCUS:LAB",
        "right": "FOCUS:DEV",
    }.get(focus or "", "OPERATOR")
    line1 = fit_line(f"{product}  ·  MISSION CONTROL  ·  {focus_tag}", width)
    line2 = fit_line(
        f"Session {session}  |  Symbol {symbol}  |  Last {last}  |  "
        f"Market {market}  |  AI {ai}  |  Health {health}",
        width,
    )
    line3 = fit_line(
        f"Decision: {decision}  |  Execution: {execution}  |  Mode: OBSERVE",
        width,
    )
    return ["=" * width, line1, line2, line3, "-" * width]


def _render_bottom(
    fields: dict[str, ProvenancedField],
    *,
    width: int,
    now: float,
) -> list[str]:
    del now
    lines = ["-" * width]
    for key in (
        "Operator Messages",
        "No Trade reasons",
        "Certification",
        "System notices",
    ):
        field = fields[key]
        lines.append(fit_line(f"  {key}: {field.value}", width))
    while len(lines) < _BOTTOM_ROWS:
        lines.append(" " * min(width, 1))
    return lines[:_BOTTOM_ROWS]


def _panel_block(
    title: str,
    fields: dict[str, ProvenancedField],
    *,
    width: int,
    rows: int,
    now: float,
    focused: bool,
) -> list[str]:
    marker = ">" if focused else " "
    lines = [
        fit_line(f"{marker}{title}", width),
        fit_line("." * max(4, min(width, len(title) + 2)), width),
    ]
    for key, field in fields.items():
        src = short_source(field.source_object)
        age = format_age_display(now, field.timestamp)
        budget = max(4, width - len(key) - 4)
        value = truncate(f"{field.value}", max(4, budget - len(src) - len(age) - 3))
        lines.append(fit_line(f"{key}", width))
        lines.append(fit_line(f"  {value} [{src}|{age}]", width))
    # Pad / trim to exact body rows (stable columns).
    if len(lines) < rows:
        lines.extend(" " * width for _ in range(rows - len(lines)))
    return [fit_line(line, width) for line in lines[:rows]]
