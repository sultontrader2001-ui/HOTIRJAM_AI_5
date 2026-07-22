"""CLI — Bridge Receiver (inbox + M1.4 HTTP)."""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from pathlib import Path

from hotirjam_bridge.metrics import BridgeMetrics
from hotirjam_bridge.receiver.http_server import run_http_receiver
from hotirjam_bridge.receiver.runtime import EnvelopeReceiverRuntime


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bridge_receiver",
        description=(
            "HOTIRJAM Bridge Receiver — unwrap envelopes to mnq_ticks/mnq_dom. "
            "Use --http for live HTTP, or --inbox for local feed."
        ),
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        help="Directory for mnq_ticks.ndjson and mnq_dom.ndjson",
    )
    parser.add_argument(
        "--inbox",
        default=None,
        help="Local NDJSON envelope inbox (offline mode)",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Enable HTTP live receiver",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--symbol", default="MNQ")
    parser.add_argument("--poll", type=float, default=0.05)
    parser.add_argument("--from-start", action="store_true")
    parser.add_argument("--max-messages", type=int, default=None)
    parser.add_argument("--dedupe-window", type=int, default=10_000)
    parser.add_argument("--status-interval", type=float, default=0.5)
    parser.add_argument("--log-file", default=None)
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
    if not args.http and not args.inbox:
        print("error: provide --http and/or --inbox", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir).expanduser()
    log_handle = None
    stream = sys.stdout
    if args.log_file:
        log_path = Path(args.log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("a", encoding="utf-8")
        stream = _TeeStream(sys.stdout, log_handle)

    metrics = BridgeMetrics()
    runtime = EnvelopeReceiverRuntime(
        out_dir=out_dir,
        symbol=args.symbol,
        poll_interval=max(0.0, float(args.poll)),
        max_messages=args.max_messages,
        dedupe_window=args.dedupe_window,
        log_stream=stream,
        metrics=metrics,
    )

    if args.http:
        stop_event = asyncio.Event()

        def _handle_signal(signum: int, _frame: object) -> None:
            runtime.request_stop()
            stop_event.set()
            stream.write(f"[BRIDGE_RECEIVER] signal={signum} shutting down\n")
            stream.flush()

        signal.signal(signal.SIGINT, _handle_signal)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _handle_signal)

        try:
            asyncio.run(
                run_http_receiver(
                    runtime=runtime,
                    metrics=metrics,
                    host=args.host,
                    port=args.port,
                    status_interval=args.status_interval,
                    status_stream=stream,
                    stop_event=stop_event,
                )
            )
        finally:
            if log_handle is not None:
                log_handle.close()
        return 0

    inbox = Path(args.inbox).expanduser()

    def _handle_signal_inbox(signum: int, _frame: object) -> None:
        runtime.request_stop()
        stream.write(f"[BRIDGE_RECEIVER] signal={signum} shutting down\n")
        stream.flush()

    signal.signal(signal.SIGINT, _handle_signal_inbox)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_signal_inbox)

    try:
        if not inbox.exists():
            inbox.parent.mkdir(parents=True, exist_ok=True)
            inbox.touch()
        stats = runtime.run_inbox(inbox, start_at_eof=not args.from_start)
    finally:
        if log_handle is not None:
            log_handle.close()

    return 0 if stats.malformed == 0 or (stats.accepted_tick + stats.accepted_dom) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
