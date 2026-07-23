#!/usr/bin/env bash
# Stop HOTIRJAM-related Mac processes only (receiver + live validator).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_hotirjam_common.sh
source "$SCRIPT_DIR/_hotirjam_common.sh"

hotirjam_discover_roots

_stop_pidfile() {
  local label="$1" pidfile="$2"
  local pid
  pid="$(_read_pidfile "$pidfile")"
  if [[ -z "$pid" ]]; then
    return 0
  fi
  if _pid_alive "$pid"; then
    info "Stopping $label (pid $pid)…"
    kill "$pid" 2>/dev/null || true
    local i
    for i in 1 2 3 4 5 6 7 8 9 10; do
      _pid_alive "$pid" || break
      sleep 0.2
    done
    if _pid_alive "$pid"; then
      warn "Force kill $label pid $pid"
      kill -9 "$pid" 2>/dev/null || true
    fi
    ok "Stopped $label (was pid $pid)."
    hotirjam_log_event "stop $label pid=$pid"
  else
    info "$label pidfile stale ($pid) — removing."
  fi
  rm -f "$pidfile"
}

_stop_related_scan() {
  local pid cmd
  local found=0
  while IFS= read -r pid; do
    [[ -z "$pid" ]] && continue
    # Never kill ourselves or the control scripts' parent shells broadly.
    if [[ "$pid" == "$$" ]] || [[ "$pid" == "$PPID" ]]; then
      continue
    fi
    cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
    [[ -z "$cmd" ]] && continue
    # Extra safety: must look like HOTIRJAM receiver/validator.
    case "$cmd" in
      *hotirjam-bridge-receiver*|*bridge_receiver*|*hotirjam_bridge.receiver*|\
      *hotirjam-ai5-live-validator*|*hotirjam_ai5.live_validator*)
        info "Stopping related process pid=$pid"
        info "  $cmd"
        kill "$pid" 2>/dev/null || true
        sleep 0.3
        if _pid_alive "$pid"; then
          kill -9 "$pid" 2>/dev/null || true
        fi
        found=1
        hotirjam_log_event "stop scanned pid=$pid"
        ;;
      *)
        ;;
    esac
  done < <(hotirjam_list_related_pids)

  if [[ "$found" -eq 0 ]]; then
    info "No additional HOTIRJAM receiver/validator processes found."
  fi
}

main() {
  bold "═══ HOTIRJAM Stop ═══"
  _stop_pidfile "Bridge Receiver" "$HOTIRJAM_RECEIVER_PID_FILE"
  _stop_pidfile "Live Validator" "$HOTIRJAM_VALIDATOR_PID_FILE"
  _stop_related_scan

  if _port_listening "$HOTIRJAM_RECEIVER_PORT"; then
    warn "Port $HOTIRJAM_RECEIVER_PORT still LISTEN — may be a non-HOTIRJAM process."
  else
    ok "Port $HOTIRJAM_RECEIVER_PORT is free."
  fi
  if _port_listening "$HOTIRJAM_DOM_PORT"; then
    warn "Port $HOTIRJAM_DOM_PORT still LISTEN."
  else
    ok "Port $HOTIRJAM_DOM_PORT is free."
  fi
}

main "$@"
