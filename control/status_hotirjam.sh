#!/usr/bin/env bash
# HOTIRJAM status — processes, ports, journals, detected entry points.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_hotirjam_common.sh
source "$SCRIPT_DIR/_hotirjam_common.sh"

hotirjam_discover_roots
hotirjam_detect_receiver || true
hotirjam_detect_live_validator || true

_status_line() {
  local label="$1" state="$2" detail="${3:-}"
  local colored
  case "$state" in
    UP|LISTEN|OK|YES) colored="${C_GREEN}${state}${C_RESET}" ;;
    DOWN|FREE|NO)     colored="${C_RED}${state}${C_RESET}" ;;
    WARN|STALE)       colored="${C_YELLOW}${state}${C_RESET}" ;;
    *)                colored="$state" ;;
  esac
  printf '  %-22s %b' "$label" "$colored"
  if [[ -n "$detail" ]]; then
    printf '  %s%s%s' "${C_DIM}" "$detail" "${C_RESET}"
  fi
  printf '\n'
}

_pid_status() {
  local label="$1" pidfile="$2"
  local pid
  pid="$(_read_pidfile "$pidfile")"
  if [[ -n "$pid" ]] && _pid_alive "$pid"; then
    _status_line "$label" "UP" "pid=$pid"
  elif [[ -n "$pid" ]]; then
    _status_line "$label" "STALE" "pidfile=$pid (dead)"
  else
    _status_line "$label" "DOWN" "no pidfile"
  fi
}

_port_status() {
  local label="$1" port="$2"
  local rc
  if _port_listening "$port"; then
    local who=""
    if command -v lsof >/dev/null 2>&1; then
      who="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | awk 'NR==2 {print $1"("$2")"}')"
    fi
    _status_line "$label" "LISTEN" ":$port ${who}"
  else
    rc=$?
    if [[ "$rc" -eq 2 ]]; then
      _status_line "$label" "WARN" ":$port (no lsof/nc to probe)"
    else
      _status_line "$label" "FREE" ":$port"
    fi
  fi
}

_file_status() {
  local label="$1" path="$2"
  if [[ -f "$path" ]]; then
    local size mtime
    size="$(wc -c <"$path" | tr -d ' ')"
    mtime="$(date -r "$path" '+%H:%M:%S' 2>/dev/null || stat -f '%Sm' -t '%H:%M:%S' "$path" 2>/dev/null || echo '?')"
    _status_line "$label" "OK" "$path ($size bytes, mtime $mtime)"
  else
    _status_line "$label" "NO" "$path"
  fi
}

main() {
  bold "═══ HOTIRJAM Control Center — Status ═══"
  echo
  info "Roots"
  printf '  AI5 root     %s\n' "$HOTIRJAM_AI5_ROOT"
  printf '  Bridge root  %s\n' "$HOTIRJAM_BRIDGE_ROOT"
  printf '  Out dir      %s\n' "$HOTIRJAM_OUT_DIR"
  printf '  Logs         %s\n' "$HOTIRJAM_LOG_DIR"
  echo

  info "Detected entry points"
  printf '  Receiver     %s\n' "${RECEIVER_LABEL:-NOT FOUND}"
  printf '  Validator    %s\n' "${VALIDATOR_LABEL:-NOT FOUND}"
  echo

  info "Processes"
  _pid_status "Bridge Receiver" "$HOTIRJAM_RECEIVER_PID_FILE"
  _pid_status "Live Validator" "$HOTIRJAM_VALIDATOR_PID_FILE"

  local scanned
  scanned="$(hotirjam_list_related_pids | tr '\n' ' ')"
  if [[ -n "${scanned// /}" ]]; then
    printf '  %-22s %s%s%s\n' "Related PIDs" "${C_DIM}" "$scanned" "${C_RESET}"
  fi
  echo

  info "Ports"
  _port_status "HTTP Receiver" "$HOTIRJAM_RECEIVER_PORT"
  _port_status "DOM (compat)" "$HOTIRJAM_DOM_PORT"
  # Current M1.4 receiver serves tick+dom on a single port (8765).
  printf '  %s%s%s\n' "${C_DIM}" \
    "(M1.4: tick+dom share :$HOTIRJAM_RECEIVER_PORT; :$HOTIRJAM_DOM_PORT is optional/compat.)" \
    "${C_RESET}"
  echo

  info "HTTP health (:$HOTIRJAM_RECEIVER_PORT)"
  local health
  if health="$(hotirjam_http_health "$HOTIRJAM_RECEIVER_PORT")"; then
    _status_line "/health" "OK" "$health"
  else
    _status_line "/health" "DOWN" "curl failed or unavailable"
  fi
  echo

  info "Journals"
  _file_status "mnq_ticks.ndjson" "$HOTIRJAM_TICK_FILE"
  _file_status "mnq_dom.ndjson" "$HOTIRJAM_DOM_FILE"
  echo

  info "Log files"
  _file_status "bridge_receiver.log" "$HOTIRJAM_RECEIVER_LOG"
  _file_status "live_validator.log" "$HOTIRJAM_VALIDATOR_LOG"
  _file_status "control_center.log" "$HOTIRJAM_CONTROL_LOG"
}

main "$@"
