"""IDC Initiative Engine page — read-only diagnostics (H-6.6.3).

Observes ValidatorFrame / InitiativeSnapshot only. Never calls evaluate(),
never mutates Initiative, lifecycle, or checkpoints.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone

from hotirjam_ai5.initiative.initiative_models import InitiativeState
from hotirjam_ai5.live_validator.models import ValidatorFrame

_NA = "NOT AVAILABLE"

# H-5 architecture-documented allowed exits (display only).
_ALLOWED_NEXT: Mapping[InitiativeState, tuple[str, ...]] = {
    InitiativeState.NONE: ("EMERGING", "DOMINANT"),
    InitiativeState.EMERGING: ("EMERGING", "DOMINANT", "EXPIRED"),
    InitiativeState.DOMINANT: ("DOMINANT", "WEAKENING", "EXPIRED"),
    InitiativeState.WEAKENING: ("DOMINANT", "WEAKENING", "EXPIRED"),
    InitiativeState.EXPIRED: ("NONE", "EMERGING", "DOMINANT"),
}

# Aligns with existing evidence-channel activity floor in confidence_from_evidence.
_LOW_CONFIDENCE = 15.0


def _fmt(value: float | None, *, digits: int = 1) -> str:
    if value is None:
        return _NA
    return f"{value:.{digits}f}"


def _fmt_time(timestamp: float | None) -> str:
    if timestamp is None:
        return _NA
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
    except (OverflowError, OSError, ValueError):
        return _fmt(timestamp, digits=0)


def _allowed_next(state: InitiativeState) -> str:
    nxt = _ALLOWED_NEXT.get(state)
    if nxt is None:
        return _NA
    return ", ".join(nxt)


def _certification_label(certifications: Mapping[str, str] | None) -> str:
    if not certifications:
        return _NA
    raw = certifications.get("initiative")
    if raw is None or str(raw).strip() == "":
        return _NA
    return str(raw).upper().replace("_", " ").strip()


def _derive_health(
    frame: ValidatorFrame | None,
    *,
    feed_status: str | None,
) -> str:
    """Presentation health badge from existing fields only."""
    if feed_status == "STALE":
        return "CRITICAL"
    if frame is None:
        return "CRITICAL"
    ini = frame.initiative
    if frame.current_price is None and ini.initiative_state is InitiativeState.NONE:
        return "CRITICAL"
    if ini.confidence < _LOW_CONFIDENCE and ini.initiative_state is not InitiativeState.NONE:
        return "WARNING"
    if ini.evidence.context == 0.0 and ini.initiative_state is not InitiativeState.NONE:
        return "WARNING"
    return "HEALTHY"


def _collect_warnings(
    frame: ValidatorFrame | None,
    *,
    feed_status: str | None,
) -> list[str]:
    warnings: list[str] = []
    if frame is None:
        warnings.append("Missing Snapshot")
        return warnings

    ini = frame.initiative
    if frame.current_price is None and ini.initiative_state is InitiativeState.NONE:
        warnings.append("Missing Snapshot")
    if ini.confidence < _LOW_CONFIDENCE:
        warnings.append("Low Confidence")
    if ini.evidence.context == 0.0:
        warnings.append("Missing Context")
    # Initiative exposes no transition journal / checkpoint age on the frame.
    warnings.append("Transition Journal Not Exposed")
    if feed_status == "STALE":
        warnings.append("Feed Interruption")
    return warnings


def render_initiative_page(
    frame: ValidatorFrame | None,
    *,
    feed_status: str | None = None,
    certifications: Mapping[str, str] | None = None,
) -> str:
    """Render the IDC Initiative Engine diagnostics page."""
    lines = [
        "==============================",
        "INITIATIVE ENGINE",
        "----------------------------------------",
    ]

    if frame is None:
        lines.extend(
            [
                f"Status            {_NA}",
                f"Health            CRITICAL",
                f"Certification     {_certification_label(certifications)}",
                f"Last Evaluation   {_NA}",
                "----------------------------------------",
                "CURRENT SNAPSHOT",
                f"Buyer Initiative  {_NA}",
                f"Seller Initiative {_NA}",
                f"Dominant Side     {_NA}",
                f"Initiative State  {_NA}",
                f"Confidence        {_NA}",
                f"Timestamp         {_NA}",
                "----------------------------------------",
                "LIFECYCLE",
                f"Current State     {_NA}",
                f"Allowed Next States {_NA}",
                "----------------------------------------",
                "EVIDENCE",
                f"Force             {_NA}",
                f"Motion            {_NA}",
                f"Pressure          {_NA}",
                f"Liquidity         {_NA}",
                f"Energy            {_NA}",
                f"Context           {_NA}",
                "----------------------------------------",
                "REASONS",
                _NA,
                "----------------------------------------",
                "TRANSITION JOURNAL",
                _NA,
                "----------------------------------------",
                "WARNINGS",
                "Missing Snapshot",
                "----------------------------------------",
                "",
                "Press Q to return",
                "",
            ]
        )
        return "\n".join(lines)

    ini = frame.initiative
    evidence = ini.evidence
    health = _derive_health(frame, feed_status=feed_status)
    status = feed_status if feed_status else ini.initiative_state.value
    reasons = list(ini.reasons) if ini.reasons else []

    lines.extend(
        [
            f"Status            {status}",
            f"Health            {health}",
            f"Certification     {_certification_label(certifications)}",
            f"Last Evaluation   {_fmt_time(ini.timestamp)}",
            "----------------------------------------",
            "CURRENT SNAPSHOT",
            f"Buyer Initiative  {_fmt(ini.buyer_initiative)}",
            f"Seller Initiative {_fmt(ini.seller_initiative)}",
            f"Dominant Side     {ini.dominant_side.value}",
            f"Initiative State  {ini.initiative_state.value}",
            f"Confidence        {_fmt(ini.confidence)}",
            f"Timestamp         {_fmt_time(ini.timestamp)}",
            "----------------------------------------",
            "LIFECYCLE",
            f"Current State     {ini.initiative_state.value}",
            f"Allowed Next States {_allowed_next(ini.initiative_state)}",
            "----------------------------------------",
            "EVIDENCE",
            f"Force             {_fmt(evidence.force)}",
            f"Motion            {_fmt(evidence.motion)}",
            f"Pressure          {_fmt(evidence.pressure)}",
            f"Liquidity         {_fmt(evidence.liquidity)}",
            f"Energy            {_fmt(evidence.energy)}",
            f"Context           {_fmt(evidence.context)}",
            "----------------------------------------",
            "REASONS",
        ]
    )
    if reasons:
        lines.extend(reasons[:16])
    else:
        lines.append(_NA)
    lines.extend(
        [
            "----------------------------------------",
            "TRANSITION JOURNAL",
            _NA,
            "----------------------------------------",
            "WARNINGS",
        ]
    )
    warnings = _collect_warnings(frame, feed_status=feed_status)
    if warnings:
        lines.extend(warnings)
    else:
        lines.append("(none)")
    lines.extend(
        [
            "----------------------------------------",
            "",
            "Press Q to return",
            "",
        ]
    )
    return "\n".join(lines)
