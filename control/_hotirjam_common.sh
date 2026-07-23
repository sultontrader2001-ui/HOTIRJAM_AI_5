#!/usr/bin/env bash
# HOTIRJAM Control Center — shared discovery and helpers (sourced only).
# Do not execute directly.

set -euo pipefail

_HOTIRJAM_COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
if [[ -t 1 ]] && [[ "${NO_COLOR:-}" == "" ]]; then
  C_RESET=$'\033[0m'
  C_BOLD=$'\033[1m'
  C_DIM=$'\033[2m'
  C_RED=$'\033[31m'
  C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m'
  C_BLUE=$'\033[34m'
  C_CYAN=$'\033[36m'
else
  C_RESET="" C_BOLD="" C_DIM="" C_RED="" C_GREEN="" C_YELLOW="" C_BLUE="" C_CYAN=""
fi

ok()   { printf '%s%s%s\n' "${C_GREEN}" "$*" "${C_RESET}"; }
warn() { printf '%s%s%s\n' "${C_YELLOW}" "$*" "${C_RESET}"; }
err()  { printf '%s%s%s\n' "${C_RED}" "$*" "${C_RESET}" >&2; }
info() { printf '%s%s%s\n' "${C_CYAN}" "$*" "${C_RESET}"; }
bold() { printf '%s%s%s\n' "${C_BOLD}" "$*" "${C_RESET}"; }

# ---------------------------------------------------------------------------
# Project discovery
# ---------------------------------------------------------------------------
_is_ai5_root() {
  local d="$1"
  [[ -f "$d/pyproject.toml" ]] || return 1
  grep -q 'name = "hotirjam-ai5"' "$d/pyproject.toml" 2>/dev/null || return 1
  [[ -d "$d/bridge" ]] || return 1
  [[ -f "$d/bridge/pyproject.toml" ]] || return 1
  grep -q 'name = "hotirjam-bridge"' "$d/bridge/pyproject.toml" 2>/dev/null
}

hotirjam_discover_roots() {
  local start candidates=()
  start="$(cd "${HOTIRJAM_AI5_ROOT:-$_HOTIRJAM_COMMON_DIR}" && pwd)"
  candidates+=("$_HOTIRJAM_COMMON_DIR/..")
  candidates+=("$start")
  candidates+=("$_HOTIRJAM_COMMON_DIR/../..")
  if [[ -n "${HOTIRJAM_AI5_ROOT:-}" ]]; then
    candidates=("$HOTIRJAM_AI5_ROOT" "${candidates[@]}")
  fi

  local c resolved
  for c in "${candidates[@]}"; do
    resolved="$(cd "$c" 2>/dev/null && pwd)" || continue
    if _is_ai5_root "$resolved"; then
      HOTIRJAM_AI5_ROOT="$resolved"
      HOTIRJAM_BRIDGE_ROOT="$resolved/bridge"
      HOTIRJAM_CONTROL_DIR="$_HOTIRJAM_COMMON_DIR"
      HOTIRJAM_LOG_DIR="${HOTIRJAM_LOG_DIR:-$resolved/logs}"
      HOTIRJAM_RUN_DIR="${HOTIRJAM_RUN_DIR:-$HOTIRJAM_LOG_DIR/control}"
      HOTIRJAM_OUT_DIR="${HOTIRJAM_OUT_DIR:-$HOTIRJAM_BRIDGE_ROOT/HOTIRJAM}"
      HOTIRJAM_TICK_FILE="$HOTIRJAM_OUT_DIR/mnq_ticks.ndjson"
      HOTIRJAM_DOM_FILE="$HOTIRJAM_OUT_DIR/mnq_dom.ndjson"
      HOTIRJAM_RECEIVER_PORT="${HOTIRJAM_RECEIVER_PORT:-8765}"
      HOTIRJAM_DOM_PORT="${HOTIRJAM_DOM_PORT:-8766}"
      HOTIRJAM_RECEIVER_PID_FILE="$HOTIRJAM_RUN_DIR/bridge_receiver.pid"
      HOTIRJAM_VALIDATOR_PID_FILE="$HOTIRJAM_RUN_DIR/live_validator.pid"
      HOTIRJAM_RECEIVER_LOG="$HOTIRJAM_LOG_DIR/bridge_receiver.log"
      HOTIRJAM_VALIDATOR_LOG="$HOTIRJAM_LOG_DIR/live_validator.log"
      HOTIRJAM_CONTROL_LOG="$HOTIRJAM_LOG_DIR/control_center.log"
      mkdir -p "$HOTIRJAM_LOG_DIR" "$HOTIRJAM_RUN_DIR" "$HOTIRJAM_OUT_DIR"
      return 0
    fi
  done
  err "HOTIRJAM AI5 root not found (need pyproject hotirjam-ai5 + bridge/)."
  err "Set HOTIRJAM_AI5_ROOT or run scripts from HOTIRJAM_AI_5/control/."
  return 1
}

# ---------------------------------------------------------------------------
# Entry-point detection (PATH first, then module fallbacks — no obsolete cmds)
# ---------------------------------------------------------------------------
hotirjam_resolve_python() {
  if [[ -n "${HOTIRJAM_PYTHON:-}" ]] && command -v "$HOTIRJAM_PYTHON" >/dev/null 2>&1; then
    command -v "$HOTIRJAM_PYTHON"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi
  return 1
}

# Sets: RECEIVER_LAUNCH (bash array via eval-safe string) and RECEIVER_LABEL
hotirjam_detect_receiver() {
  local py
  if command -v hotirjam-bridge-receiver >/dev/null 2>&1; then
    RECEIVER_BIN="$(command -v hotirjam-bridge-receiver)"
    RECEIVER_LABEL="hotirjam-bridge-receiver"
    return 0
  fi
  if command -v bridge_receiver >/dev/null 2>&1; then
    RECEIVER_BIN="$(command -v bridge_receiver)"
    RECEIVER_LABEL="bridge_receiver"
    return 0
  fi
  py="$(hotirjam_resolve_python)" || {
    err "No bridge receiver CLI and no python3."
    return 1
  }
  if [[ -d "$HOTIRJAM_BRIDGE_ROOT/src/hotirjam_bridge" ]]; then
    RECEIVER_BIN="$py"
    RECEIVER_MODULE=1
    RECEIVER_LABEL="python -m hotirjam_bridge.receiver"
    return 0
  fi
  err "Cannot detect bridge receiver (install hotirjam-bridge or keep bridge/src)."
  return 1
}

hotirjam_detect_live_validator() {
  local py
  if command -v hotirjam-ai5-live-validator >/dev/null 2>&1; then
    VALIDATOR_BIN="$(command -v hotirjam-ai5-live-validator)"
    VALIDATOR_LABEL="hotirjam-ai5-live-validator"
    VALIDATOR_MODULE=0
    return 0
  fi
  py="$(hotirjam_resolve_python)" || {
    err "No Live Validator CLI and no python3."
    return 1
  }
  if [[ -d "$HOTIRJAM_AI5_ROOT/src/hotirjam_ai5/live_validator" ]]; then
    VALIDATOR_BIN="$py"
    VALIDATOR_MODULE=1
    VALIDATOR_LABEL="python -m hotirjam_ai5.live_validator.app"
    return 0
  fi
  err "Cannot detect Live Validator (install hotirjam-ai5 or keep src/hotirjam_ai5)."
  return 1
}

# Build argv into global arrays RECEIVER_CMD / VALIDATOR_CMD
hotirjam_build_receiver_cmd() {
  hotirjam_detect_receiver
  RECEIVER_CMD=()
  if [[ "${RECEIVER_MODULE:-0}" == "1" ]]; then
    RECEIVER_CMD=(
      env "PYTHONPATH=${HOTIRJAM_BRIDGE_ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
      "$RECEIVER_BIN" -m hotirjam_bridge.receiver
    )
  else
    RECEIVER_CMD=("$RECEIVER_BIN")
  fi
  RECEIVER_CMD+=(
    --http
    --out-dir "$HOTIRJAM_OUT_DIR"
    --host "${HOTIRJAM_RECEIVER_HOST:-0.0.0.0}"
    --port "$HOTIRJAM_RECEIVER_PORT"
    --symbol "${HOTIRJAM_SYMBOL:-MNQ}"
    --log-file "$HOTIRJAM_RECEIVER_LOG"
  )
}

hotirjam_build_validator_cmd() {
  hotirjam_detect_live_validator
  VALIDATOR_CMD=()
  if [[ "${VALIDATOR_MODULE:-0}" == "1" ]]; then
    VALIDATOR_CMD=(
      env "PYTHONPATH=${HOTIRJAM_AI5_ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
      "$VALIDATOR_BIN" -m hotirjam_ai5.live_validator.app
    )
  else
    VALIDATOR_CMD=("$VALIDATOR_BIN")
  fi
  # Prefer explicit tick file written by the Mac bridge receiver.
  if [[ -f "$HOTIRJAM_TICK_FILE" ]] || [[ -d "$HOTIRJAM_OUT_DIR" ]]; then
    VALIDATOR_CMD+=(--tick-file "$HOTIRJAM_TICK_FILE")
  fi
  VALIDATOR_CMD+=(--symbol "${HOTIRJAM_SYMBOL:-MNQ}")
}

# ---------------------------------------------------------------------------
# Process helpers — HOTIRJAM-related only
# ---------------------------------------------------------------------------
# Patterns must stay narrow: never pkill -f python alone.
HOTIRJAM_PGREP_PATTERNS=(
  'hotirjam-bridge-receiver'
  'bridge_receiver'
  'hotirjam_bridge\.receiver'
  'hotirjam-ai5-live-validator'
  'hotirjam_ai5\.live_validator'
)

_pid_alive() {
  local pid="${1:-}"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

_read_pidfile() {
  local f="$1"
  if [[ -f "$f" ]]; then
    tr -d '[:space:]' <"$f" || true
  fi
}

_write_pidfile() {
  local f="$1" pid="$2"
  printf '%s\n' "$pid" >"$f"
}

hotirjam_list_related_pids() {
  local pat pids=""
  for pat in "${HOTIRJAM_PGREP_PATTERNS[@]}"; do
    pids+=" $(pgrep -f "$pat" 2>/dev/null || true)"
  done
  # Unique numeric PIDs
  printf '%s\n' $pids | awk '/^[0-9]+$/ {print}' | sort -u
}

_port_listening() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi
  if command -v nc >/dev/null 2>&1; then
    nc -z 127.0.0.1 "$port" >/dev/null 2>&1
    return $?
  fi
  return 2
}

hotirjam_http_health() {
  local port="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -fsS --max-time 2 "http://127.0.0.1:${port}/health" 2>/dev/null || return 1
    return 0
  fi
  return 2
}

hotirjam_stamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

hotirjam_log_event() {
  printf '[%s] %s\n' "$(hotirjam_stamp)" "$*" >>"$HOTIRJAM_CONTROL_LOG"
}
