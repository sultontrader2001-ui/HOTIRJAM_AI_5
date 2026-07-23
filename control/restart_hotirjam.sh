#!/usr/bin/env bash
# Restart HOTIRJAM Mac host stack.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bold_msg() { printf '\033[1m%s\033[0m\n' "$*"; }

bold_msg "═══ HOTIRJAM Restart ═══"
"$SCRIPT_DIR/stop_hotirjam.sh"
sleep 0.5
"$SCRIPT_DIR/start_hotirjam.sh"
