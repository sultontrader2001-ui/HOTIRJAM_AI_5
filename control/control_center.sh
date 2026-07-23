#!/usr/bin/env bash
# HOTIRJAM Control Center v1 — interactive menu.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_hotirjam_common.sh
source "$SCRIPT_DIR/_hotirjam_common.sh"

hotirjam_discover_roots

_banner() {
  clear 2>/dev/null || true
  bold "╔══════════════════════════════════════════╗"
  bold "║     HOTIRJAM Control Center v1           ║"
  bold "╚══════════════════════════════════════════╝"
  printf '%sAI5%s  %s\n' "${C_DIM}" "${C_RESET}" "$HOTIRJAM_AI5_ROOT"
  printf '%sLogs%s %s\n' "${C_DIM}" "${C_RESET}" "$HOTIRJAM_LOG_DIR"
  echo
}

_menu() {
  echo "  1) Start System"
  echo "  2) Stop System"
  echo "  3) Restart System"
  echo "  4) Status"
  echo "  5) Live Logs"
  echo "  6) Exit"
  echo
}

_live_logs() {
  echo
  info "Live logs — pick a stream (Ctrl-C returns to menu):"
  echo "  1) Bridge Receiver  ($HOTIRJAM_RECEIVER_LOG)"
  echo "  2) Live Validator   ($HOTIRJAM_VALIDATOR_LOG)"
  echo "  3) Control Center   ($HOTIRJAM_CONTROL_LOG)"
  echo "  4) Tick journal     ($HOTIRJAM_TICK_FILE)"
  echo "  5) Back"
  local choice
  read -r -p "Log> " choice || return 0
  local target=""
  case "$choice" in
    1) target="$HOTIRJAM_RECEIVER_LOG" ;;
    2) target="$HOTIRJAM_VALIDATOR_LOG" ;;
    3) target="$HOTIRJAM_CONTROL_LOG" ;;
    4) target="$HOTIRJAM_TICK_FILE" ;;
    5|"") return 0 ;;
    *) warn "Unknown choice."; sleep 1; return 0 ;;
  esac
  if [[ ! -f "$target" ]]; then
    warn "File not found yet: $target"
    touch "$target" 2>/dev/null || true
  fi
  info "tail -f $target"
  echo
  # Intentionally do not use set -e around tail (Ctrl-C).
  set +e
  tail -n 40 -f "$target"
  set -e
}

_pause() {
  echo
  read -r -p "Press Enter to continue…" _ || true
}

main() {
  hotirjam_log_event "control_center open"
  while true; do
    _banner
    _menu
    local choice
    read -r -p "Select> " choice || choice=6
    case "$choice" in
      1)
        "$SCRIPT_DIR/start_hotirjam.sh" || true
        _pause
        ;;
      2)
        "$SCRIPT_DIR/stop_hotirjam.sh" || true
        _pause
        ;;
      3)
        "$SCRIPT_DIR/restart_hotirjam.sh" || true
        _pause
        ;;
      4)
        "$SCRIPT_DIR/status_hotirjam.sh" || true
        _pause
        ;;
      5)
        _live_logs
        ;;
      6|q|Q|exit)
        info "Goodbye."
        hotirjam_log_event "control_center exit"
        exit 0
        ;;
      *)
        warn "Invalid option: $choice"
        sleep 1
        ;;
    esac
  done
}

main "$@"
