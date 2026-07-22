"""CLI for H-8.0 Live Observation & Certification."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hotirjam_ai5.observation.session import ObservationSession


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hotirjam-ai5-observe",
        description=(
            "HOTIRJAM AI 5 H-8.0 — Live Observation & Certification. "
            "Observe only. No orders. No RuntimeHub mutation."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=("live", "hub", "demo"),
        default="live",
        help="live=tick file, hub=read RuntimeHub, demo=synthetic ticks",
    )
    parser.add_argument("--tick-file", default=None, help="NT01 NDJSON tick path")
    parser.add_argument("--max-cycles", type=int, default=50)
    parser.add_argument("--min-cycles", type=int, default=1)
    parser.add_argument("--max-seconds", type=float, default=60.0)
    parser.add_argument("--poll", type=float, default=0.05)
    parser.add_argument(
        "--report",
        default=None,
        help="Optional path to write certification report text",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    session = ObservationSession(min_cycles=max(1, args.min_cycles))

    if args.mode == "hub":
        report = session.observe_hub(
            max_cycles=args.max_cycles,
            poll_seconds=args.poll,
            max_seconds=args.max_seconds,
        )
    elif args.mode == "demo":
        report = _run_demo(session, max_cycles=args.max_cycles)
    else:
        report = session.observe_live_file(
            tick_path=args.tick_file,
            max_cycles=args.max_cycles,
            max_seconds=args.max_seconds,
            poll_seconds=args.poll,
        )

    text = report.as_text()
    print(text)
    if args.report:
        path = Path(args.report).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        print(f"Report written: {path}")

    return 0 if report.verdict == "PASS" else 1


def _run_demo(session: ObservationSession, *, max_cycles: int) -> object:
    """Synthetic ticks for offline certification (no live file required)."""
    from hotirjam_ai5.live_data.tick import LiveTick

    ticks = []
    for i in range(max(max_cycles * 3, 30)):
        px = 18000.0 + (i % 7) * 0.25
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
    return session.observe_live(ticks, max_cycles=max_cycles)


if __name__ == "__main__":
    sys.exit(main())
