"""Allow: python -m hotirjam_bridge sender|receiver ...

Windows-safe fallback when Scripts\\ is not on PATH.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        print(
            "usage: python -m hotirjam_bridge {sender|receiver} [options]\n"
            "\n"
            "Windows examples:\n"
            "  python -m hotirjam_bridge sender --help\n"
            "  python -m hotirjam_bridge.sender --help\n"
            "  python -m hotirjam_bridge receiver --help\n"
            "\n"
            "After: cd bridge; python -m pip install -e .\n"
            "Console scripts (if Scripts on PATH):\n"
            "  bridge_sender / hotirjam-bridge-sender\n"
            "  bridge_receiver / hotirjam-bridge-receiver\n"
        )
        return 0

    cmd = args[0]
    rest = args[1:]
    if cmd in {"sender", "bridge_sender", "hotirjam-bridge-sender"}:
        from hotirjam_bridge.sender.app import main as sender_main

        return int(sender_main(rest))
    if cmd in {"receiver", "bridge_receiver", "hotirjam-bridge-receiver"}:
        from hotirjam_bridge.receiver.app import main as receiver_main

        return int(receiver_main(rest))

    print(f"unknown command: {cmd!r} (expected sender|receiver)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
