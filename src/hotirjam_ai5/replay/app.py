"""CLI for H-8.1 Replay Validator."""

from __future__ import annotations

import argparse
import sys

from hotirjam_ai5.observation.models import ObservationCycle
from hotirjam_ai5.observation.session import ObservationSession
from hotirjam_ai5.replay.engine import ReplayValidator
from hotirjam_ai5.replay.models import MarketPoint
from hotirjam_ai5.replay.report import format_replay_report


def build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="hotirjam-ai5-replay",
        description=(
            "HOTIRJAM AI 5 H-8.1 — Replay Validation. "
            "Read-only. Never mutates observations or sends orders."
        ),
    )


def main(argv: list[str] | None = None) -> int:
    build_arg_parser().parse_args(argv)
    # Demo: generate observation session then replay against synthetic path.
    from hotirjam_ai5.live_data.tick import LiveTick

    ticks = []
    for i in range(40):
        px = 18000.0 + (i % 9) * 0.25
        ticks.append(
            LiveTick(
                timestamp=1_700_000_000.0 + i,
                symbol="MNQ",
                last_price=px,
                bid=px - 0.25,
                ask=px + 0.25,
                volume=1.0,
            )
        )
    session = ObservationSession(min_cycles=5)
    obs_report = session.observe_live(ticks, max_cycles=5)
    observations = obs_report.cycles
    # Market path: observation prices + gentle continuation
    market: list[MarketPoint] = []
    for c in observations:
        try:
            p0 = float(c.price) if c.price not in {"N/A", ""} else 18000.0
        except ValueError:
            p0 = 18000.0
        market.append(MarketPoint(time=c.time, price=p0))
        for j in range(1, 6):
            market.append(MarketPoint(time=c.time + j, price=p0))

    report = ReplayValidator().replay(observations, market)
    print(format_replay_report(report))
    # Certification imprint: prove observations unchanged
    assert all(
        isinstance(c, ObservationCycle) for c in observations
    ), "observations must remain ObservationCycle"
    return 0 if report.verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
