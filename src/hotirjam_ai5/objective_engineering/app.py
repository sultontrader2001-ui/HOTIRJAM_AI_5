"""CLI — Objective Engine V2 Engineering Validation Phase A."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from hotirjam_ai5.objective_engineering.session import EngineeringValidationSession


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hotirjam-ai5-objective-ev",
        description=(
            "Objective Engine V2 Engineering Validation Phase A. "
            "Collect live evidence and highlight anomalies. "
            "Does NOT certify. Does NOT formal-validate. "
            "Does NOT change Objective logic."
        ),
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Evidence directory (default: logs/objective_ev/session_<utc>)",
    )
    parser.add_argument("--tick-file", default=None, help="NT01 mnq_ticks.ndjson path")
    parser.add_argument("--symbol", default="MNQ")
    parser.add_argument("--tick-size", type=float, default=0.25)
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=3600.0,
        help="Live poll duration (default 3600)",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Stop after N evaluates (optional)",
    )
    parser.add_argument("--poll", type=float, default=0.05)
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Synthetic ticks (offline smoke); not a live session",
    )
    parser.add_argument(
        "--demo-ticks",
        type=int,
        default=80,
        help="Synthetic tick count when --demo",
    )
    return parser


def _default_out_dir() -> Path:
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("logs") / "objective_ev" / f"session_{stamp}"


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    out_dir = Path(args.out_dir).expanduser() if args.out_dir else _default_out_dir()
    session = EngineeringValidationSession(out_dir=out_dir)

    if args.demo:
        report = session.run_ticks(
            _demo_ticks(count=max(1, args.demo_ticks)),
            max_samples=args.max_samples,
            tick_size=args.tick_size,
            symbol=args.symbol,
        )
    else:
        report = session.run_live_file(
            tick_path=args.tick_file,
            max_samples=args.max_samples,
            max_seconds=args.max_seconds,
            poll_seconds=args.poll,
            tick_size=args.tick_size,
            symbol=args.symbol,
        )

    text = report.as_text()
    print(text)
    print(f"Report written: {out_dir / 'session_report.txt'}")
    return 0 if report.workflow_verdict == "PASS" else 1


def _demo_ticks(*, count: int):
    from hotirjam_ai5.live_data.tick import LiveTick

    ticks = []
    for i in range(count):
        # Mild oscillation so swings/objectives can appear over bars.
        px = 18000.0 + (i % 11) * 0.25 - (i // 20) * 0.5
        ticks.append(
            LiveTick(
                timestamp=1_700_000_000.0 + i * 0.25,
                symbol="MNQ",
                last_price=px,
                bid=px - 0.25,
                ask=px + 0.25,
                volume=1.0,
            )
        )
    return ticks


if __name__ == "__main__":
    raise SystemExit(main())
