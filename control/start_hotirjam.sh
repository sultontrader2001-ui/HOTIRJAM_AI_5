#!/usr/bin/env bash
# Start HOTIRJAM Mac host stack: Bridge Receiver (+ Live Validator).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_hotirjam_common.sh
source "$SCRIPT_DIR/_hotirjam_common.sh"

hotirjam_discover_roots
hotirjam_build_receiver_cmd
hotirjam_build_validator_cmd

START_VALIDATOR="${HOTIRJAM_START_VALIDATOR:-1}"

_start_receiver() {
  local existing
  existing="$(_read_pidfile "$HOTIRJAM_RECEIVER_PID_FILE")"
  if _pid_alive "$existing"; then
    warn "Bridge Receiver already running (pid $existing)."
    return 0
  fi
  if _port_listening "$HOTIRJAM_RECEIVER_PORT"; then
    warn "Port $HOTIRJAM_RECEIVER_PORT already listening — not starting a second receiver."
    return 0
  fi

  info "Starting Bridge Receiver ($RECEIVER_LABEL)…"
  info "  out-dir: $HOTIRJAM_OUT_DIR"
  info "  port:    $HOTIRJAM_RECEIVER_PORT"
  info "  log:     $HOTIRJAM_RECEIVER_LOG"

  (
    cd "$HOTIRJAM_BRIDGE_ROOT"
    # Receiver status board goes to stdout; keep a dedicated log via --log-file.
    nohup "${RECEIVER_CMD[@]}" >>"$HOTIRJAM_RECEIVER_LOG" 2>>"$HOTIRJAM_RECEIVER_LOG" &
    echo $! >"$HOTIRJAM_RECEIVER_PID_FILE"
  )
  sleep 0.6

  local pid
  pid="$(_read_pidfile "$HOTIRJAM_RECEIVER_PID_FILE")"
  if ! _pid_alive "$pid"; then
    err "Bridge Receiver failed to stay up. See $HOTIRJAM_RECEIVER_LOG"
    hotirjam_log_event "receiver start FAILED"
    return 1
  fi

  if _port_listening "$HOTIRJAM_RECEIVER_PORT"; then
    ok "Bridge Receiver UP  pid=$pid  :$HOTIRJAM_RECEIVER_PORT"
  else
    warn "Bridge Receiver pid=$pid but port $HOTIRJAM_RECEIVER_PORT not listening yet."
  fi
  hotirjam_log_event "receiver start pid=$pid"
}

_start_validator_background() {
  local existing
  existing="$(_read_pidfile "$HOTIRJAM_VALIDATOR_PID_FILE")"
  if _pid_alive "$existing"; then
    warn "Live Validator already running (pid $existing)."
    return 0
  fi

  info "Starting Live Validator ($VALIDATOR_LABEL)…"
  info "  tick: $HOTIRJAM_TICK_FILE"
  info "  log:  $HOTIRJAM_VALIDATOR_LOG"

  (
    cd "$HOTIRJAM_AI5_ROOT"
    nohup "${VALIDATOR_CMD[@]}" >>"$HOTIRJAM_VALIDATOR_LOG" 2>>"$HOTIRJAM_VALIDATOR_LOG" &
    echo $! >"$HOTIRJAM_VALIDATOR_PID_FILE"
  )
  sleep 0.4

  local pid
  pid="$(_read_pidfile "$HOTIRJAM_VALIDATOR_PID_FILE")"
  if _pid_alive "$pid"; then
    ok "Live Validator UP  pid=$pid"
    warn "Dashboard is TTY-oriented; use an interactive terminal for the full UI."
    hotirjam_log_event "validator start pid=$pid"
    return 0
  fi
  err "Live Validator failed to stay up. See $HOTIRJAM_VALIDATOR_LOG"
  hotirjam_log_event "validator start FAILED"
  return 1
}

_start_validator_macos_terminal() {
  local launcher
  launcher="$SCRIPT_DIR/run_live_validator.sh"
  chmod +x "$launcher" 2>/dev/null || true
  # Pass absolute path; Terminal runs a login shell that sources the launcher.
  osascript \
    -e 'tell application "Terminal" to activate' \
    -e "tell application \"Terminal\" to do script \"exec $(printf %q "$launcher")\""
  ok "Live Validator launched in a new Terminal window."
  hotirjam_log_event "validator start via Terminal.app"
}

_start_validator() {
  if [[ "$START_VALIDATOR" != "1" ]]; then
    info "Skipping Live Validator (HOTIRJAM_START_VALIDATOR=$START_VALIDATOR)."
    return 0
  fi
  if [[ "$(uname -s)" == "Darwin" ]] && command -v osascript >/dev/null 2>&1 \
    && [[ "${HOTIRJAM_VALIDATOR_MODE:-terminal}" == "terminal" ]]; then
    _start_validator_macos_terminal || _start_validator_background
  else
    _start_validator_background
  fi
}

main() {
  bold "═══ HOTIRJAM Start ═══"
  info "AI5:    $HOTIRJAM_AI5_ROOT"
  info "Bridge: $HOTIRJAM_BRIDGE_ROOT"
  _start_receiver
  _start_validator
  echo
  info "Tip: ./status_hotirjam.sh"
}

main "$@"
