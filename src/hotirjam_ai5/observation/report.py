"""Certification report for an observation session (H-8.0)."""

from __future__ import annotations

from dataclasses import dataclass

from hotirjam_ai5.observation.models import ObservationCycle

_REQUIRED = (
    "time",
    "objective",
    "initiative",
    "response",
    "continuation",
    "break_capability",
    "confidence",
    "market_state",
    "evidence",
    "no_trade_reason",
    "decision",
)

_FORBIDDEN_DECISIONS = frozenset(
    {
        "BUY",
        "SELL",
        "BUY_MARKET",
        "SELL_MARKET",
        "SUBMIT",
        "ORDER",
        "LIVE_BUY",
        "LIVE_SELL",
    }
)


@dataclass(frozen=True, slots=True)
class CertificationReport:
    """End-of-session certification artifact."""

    verdict: str  # PASS | FAIL
    cycle_count: int
    duration_seconds: float
    symbol: str
    reasons: tuple[str, ...]
    summary_lines: tuple[str, ...]
    cycles: tuple[ObservationCycle, ...]

    def as_text(self) -> str:
        lines = [
            "HOTIRJAM AI 5 — H-8.0 Live Observation Certification",
            "=" * 60,
            f"Verdict: {self.verdict}",
            f"Cycles: {self.cycle_count}",
            f"Duration: {self.duration_seconds:.3f}s",
            f"Symbol: {self.symbol}",
            "",
            "Reasons:",
        ]
        for reason in self.reasons:
            lines.append(f"  - {reason}")
        lines.append("")
        lines.append("Observation summary:")
        for row in self.summary_lines:
            lines.append(f"  {row}")
        lines.append("")
        lines.append("Mode: OBSERVE only · No orders · No RuntimeHub mutation")
        lines.append("=" * 60)
        return "\n".join(lines)


def build_certification_report(
    cycles: tuple[ObservationCycle, ...] | list[ObservationCycle],
    *,
    duration_seconds: float,
    min_cycles: int = 1,
    orders_attempted: int = 0,
    hub_mutated: bool = False,
) -> CertificationReport:
    """Certify an observation session. PASS only when all gates clear."""
    records = tuple(cycles)
    reasons: list[str] = []
    ok = True

    if orders_attempted != 0:
        ok = False
        reasons.append(f"Orders attempted: {orders_attempted} (must be 0)")
    else:
        reasons.append("No orders attempted")

    if hub_mutated:
        ok = False
        reasons.append("RuntimeHub was mutated by observation layer")
    else:
        reasons.append("RuntimeHub not mutated by observation layer")

    if len(records) < min_cycles:
        ok = False
        reasons.append(f"Insufficient cycles: {len(records)} < {min_cycles}")
    else:
        reasons.append(f"Recorded cycles OK: {len(records)} >= {min_cycles}")

    for cycle in records:
        for field in _REQUIRED:
            value = getattr(cycle, field)
            if value is None or str(value).strip() == "":
                ok = False
                reasons.append(f"Cycle {cycle.cycle_id}: missing {field}")
        decision_u = str(cycle.decision).upper().strip()
        if decision_u in _FORBIDDEN_DECISIONS:
            ok = False
            reasons.append(
                f"Cycle {cycle.cycle_id}: forbidden live decision '{cycle.decision}'"
            )

    if ok and not any(r.startswith("Cycle ") for r in reasons):
        reasons.append("All cycles have required observation fields")
        reasons.append("No forbidden live trading decisions")

    symbol = records[-1].symbol if records else "N/A"
    summary = _summarize(records)
    return CertificationReport(
        verdict="PASS" if ok else "FAIL",
        cycle_count=len(records),
        duration_seconds=float(duration_seconds),
        symbol=symbol,
        reasons=tuple(reasons),
        summary_lines=tuple(summary),
        cycles=records,
    )


def _summarize(records: tuple[ObservationCycle, ...]) -> list[str]:
    if not records:
        return ["No cycles recorded"]
    decisions: dict[str, int] = {}
    for c in records:
        decisions[c.decision] = decisions.get(c.decision, 0) + 1
    first, last = records[0], records[-1]
    lines = [
        f"First cycle t={first.time:.3f} decision={first.decision} "
        f"obj={first.objective}",
        f"Last cycle t={last.time:.3f} decision={last.decision} "
        f"obj={last.objective}",
        f"Decision histogram: {decisions}",
        f"Last confidence={last.confidence} market_state={last.market_state}",
        f"Last no_trade_reason={last.no_trade_reason}",
    ]
    return lines
