#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVER="$REPO_DIR/dashboard/server_v2.py"
LOG_DIR="$REPO_DIR/logs"
RUN_DIR="$REPO_DIR/run"
LOG_FILE="$LOG_DIR/dashboard-runtime.log"
PID_FILE="$RUN_DIR/dashboard.pid"
PORT="19100"

mkdir -p "$LOG_DIR" "$RUN_DIR"

find_pid() {
  if [ -f "$PID_FILE" ]; then
    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      printf '%s\n' "$pid"
      return 0
    fi
  fi

  local pid
  pid="$(ps -eo pid=,comm=,args= | awk '/python3/ && /resonantos-alpha\/dashboard\/server_v2\.py/ {print $1; exit}')"
  if [ -n "$pid" ]; then
    printf '%s\n' "$pid"
    return 0
  fi
  return 1
}

wait_http() {
  local url="$1"
  local seconds="${2:-30}"
  local i
  for i in $(seq 1 "$seconds"); do
    if curl -sf --max-time 3 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

start_dashboard() {
  if pid="$(find_pid 2>/dev/null)"; then
    echo "dashboard already running (pid=$pid)"
    exit 0
  fi

  cd "$REPO_DIR/dashboard"
  nohup /usr/bin/python3 -u "$SERVER" >>"$LOG_FILE" 2>&1 &
  local pid=$!
  echo "$pid" > "$PID_FILE"

  if wait_http "http://127.0.0.1:${PORT}/api/gateway/token" 45; then
    echo "dashboard started (pid=$pid)"
  else
    echo "dashboard failed to start; recent log:"
    tail -n 80 "$LOG_FILE" || true
    exit 1
  fi
}

stop_dashboard() {
  local pid=""
  if pid="$(find_pid 2>/dev/null)"; then
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 40); do
      if ! kill -0 "$pid" 2>/dev/null; then
        rm -f "$PID_FILE"
        echo "dashboard stopped"
        return 0
      fi
      sleep 0.2
    done
    kill -9 "$pid" 2>/dev/null || true
    rm -f "$PID_FILE"
    echo "dashboard killed"
  else
    rm -f "$PID_FILE"
    echo "dashboard not running"
  fi
}

status_dashboard() {
  echo "repo=$(cd "$REPO_DIR" && git rev-parse --short HEAD)"
  echo "branch=$(cd "$REPO_DIR" && git branch --show-current)"
  echo "version=$(cat "$REPO_DIR/VERSION")"
  if pid="$(find_pid 2>/dev/null)"; then
    echo "pid=$pid"
    ps -p "$pid" -o pid=,ppid=,user=,etime=,cmd=
  else
    echo "pid=not-running"
  fi
  echo "listener:"
  ss -ltnp | grep ":${PORT}\\b" || true
}

check_dashboard() {
  echo "loopback_root=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:${PORT}/" || true)"
  echo "setup=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:${PORT}/setup" || true)"
  echo "gateway_token=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:${PORT}/api/gateway/token" || true)"
  echo "chat_redirect=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:${PORT}/chat-redirect" || true)"
  if command -v tailscale >/dev/null 2>&1; then
    local ts_ip
    ts_ip="$(tailscale ip -4 2>/dev/null | head -n 1 || true)"
    if [ -n "$ts_ip" ]; then
      echo "tailscale_ip=$ts_ip"
      echo "tailscale_root=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://${ts_ip}:${PORT}/" || true)"
    fi
  fi
}

logs_dashboard() {
  local lines="${1:-60}"
  tail -n "$lines" "$LOG_FILE"
}

case "${1:-status}" in
  start) start_dashboard ;;
  stop) stop_dashboard ;;
  restart) stop_dashboard; start_dashboard ;;
  status) status_dashboard ;;
  check) check_dashboard ;;
  logs) logs_dashboard "${2:-60}" ;;
  *)
    echo "usage: $0 {start|stop|restart|status|check|logs [lines]}" >&2
    exit 2
    ;;
esac
