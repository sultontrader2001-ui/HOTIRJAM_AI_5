#!/usr/bin/env bash
# Launcher for Live Validator in an interactive Terminal (macOS).
# Invoked by start_hotirjam.sh via Terminal.app — not for general use.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_hotirjam_common.sh
source "$SCRIPT_DIR/_hotirjam_common.sh"

hotirjam_discover_roots
hotirjam_build_validator_cmd

cd "$HOTIRJAM_AI5_ROOT"
exec "${VALIDATOR_CMD[@]}"
