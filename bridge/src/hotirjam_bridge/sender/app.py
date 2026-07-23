"""CLI — Bridge Sender (M1.2 log-only + M1.4 HTTP)."""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from pathlib import Path

from hotirjam_bridge.sender.http_runtime import HttpSenderRuntime
from hotirjam_bridge.sender.runtime import TickSenderRuntime


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bridge_sender",
        description=(
            "HOTIRJAM Bridge Sender — tail NT01 ticks, envelope, "
            "optional HTTP POST to Mac Receiver."
        ),
    )
    parser.add_argument("--tick-file", required=True, help="Path to mnq_ticks.ndjson")
    parser.add_argument("--dom-file", default=None, help="Optional mnq_dom.ndjson")
    parser.add_argument("--symbol", default="MNQ")
    parser.add_argument("--poll", type=float, default=0.05)
    parser.add_argument("--from-start", action="store_true")
    parser.add_argument("--max-ticks", type=int, default=None)
    parser.add_argument("--log-file", default=None)
    parser.add_argument(
        "--url",
        default=None,
        help="Receiver base URL (e.g. http://127.0.0.1:8765). Enables HTTP mode.",
    )
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--retry-delay", type=float, default=0.2)
    parser.add_argument("--heartbeat", type=float, default=1.0)
    parser.add_argument("--status-interval", type=float, default=0.5)
    return parser


class _TeeStream:
    def __init__(self, *streams) -> None:
        self._streams = streams

    def write(self, data: str) -> int:
        for stream in self._streams:
            stream.write(data)
            stream.flush()
        return len(data)

    def flush(self) -> None:
        for stream in self._streams:
            stream.flush()


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    tick_file = Path(args.tick_file).expanduser()
    # Always pair DOM with the tick journal folder unless --dom-file overrides.
    # Missing file is OK — NdjsonTail waits; omitting DOM entirely was leaving
    # ticks live while Dashboard DOM Health stayed DISCONNECTED forever.
    if args.dom_file:
        dom_file: Path | None = Path(args.dom_file).expanduser()
    else:
        dom_file = tick_file.with_name("mnq_dom.ndjson")

    log_handle = None
    stream = sys.stdout
    if args.log_file:
        log_path = Path(args.log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("a", encoding="utf-8")
        stream = _TeeStream(sys.stdout, log_handle)

    if args.url:
        stream.write(
            f"[BRIDGE_SENDER] DOM journal={dom_file} "
            f"exists={dom_file.is_file()}\n"
        )
        stream.flush()
        runtime = HttpSenderRuntime(
            tick_file=tick_file,
            dom_file=dom_file,
            base_url=args.url,
            symbol=args.symbol,
            poll_interval=max(0.0, float(args.poll)),
            start_at_eof=not args.from_start,
            max_ticks=args.max_ticks,
            timeout=args.timeout,
            max_retries=args.retries,
            retry_delay=args.retry_delay,
            heartbeat_interval=args.heartbeat,
            status_interval=args.status_interval,
            log_stream=stream,
        )

        def _handle_signal(signum: int, _frame: object) -> None:
            runtime.request_stop()
            stream.write(f"[BRIDGE_SENDER] signal={signum} shutting down\n")
            stream.flush()

        signal.signal(signal.SIGINT, _handle_signal)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _handle_signal)

        try:
            metrics = asyncio.run(runtime.run())
        finally:
            if log_handle is not None:
                log_handle.close()
        return 0 if metrics.tick_sent > 0 or metrics.send_failures == 0 else 1

    runtime = TickSenderRuntime(
        tick_file=tick_file,
        symbol=args.symbol,
        poll_interval=max(0.0, float(args.poll)),
        start_at_eof=not args.from_start,
        max_ticks=args.max_ticks,
        log_stream=stream,
    )

    def _handle_signal_local(signum: int, _frame: object) -> None:
        runtime.request_stop()
        stream.write(f"[BRIDGE_SENDER] signal={signum} shutting down\n")
        stream.flush()

    signal.signal(signal.SIGINT, _handle_signal_local)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_signal_local)

    try:
        stats = runtime.run()
    finally:
        if log_handle is not None:
            log_handle.close()

    return 0 if stats.malformed == 0 or stats.ticks_accepted > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
