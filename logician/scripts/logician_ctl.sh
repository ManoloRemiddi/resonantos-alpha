#!/bin/bash
# Logician Control Script (Linux-safe)
# Usage: ./logician_ctl.sh [build|start|stop|restart|status|health|query|logs]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOGICIAN_DIR="$(dirname "$SCRIPT_DIR")"
REPO_DIR="$(dirname "$LOGICIAN_DIR")"
SERVICE_DIR="$LOGICIAN_DIR/mangle-service"
RULES_FILE="$LOGICIAN_DIR/poc/production_rules.mg"
SOCK_PATH="${MANGLE_SOCK:-/tmp/mangle.sock}"
PROXY_DIR="$REPO_DIR/logician-proxy"
PROXY_PORT="${LOGICIAN_PROXY_PORT:-8081}"
LOG_DIR="$LOGICIAN_DIR/logs"
RUN_DIR="$REPO_DIR/run"
SERVER_PID_FILE="$RUN_DIR/logician.pid"
PROXY_PID_FILE="$RUN_DIR/logician-proxy.pid"
SERVER_LOG="$LOG_DIR/logician.log"
SERVER_ERR="$LOG_DIR/logician_error.log"
PROXY_LOG="$LOG_DIR/logician_proxy.log"

mkdir -p "$LOG_DIR" "$RUN_DIR"

is_pid_running() {
  local pid="$1"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

pid_from_file() {
  local file="$1"
  if [ -f "$file" ]; then
    tr -d '[:space:]' < "$file"
  fi
}

stop_pid_file() {
  local file="$1"
  local pid
  pid="$(pid_from_file "$file")"
  if [ -n "${pid:-}" ] && is_pid_running "$pid"; then
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 25); do
      if ! is_pid_running "$pid"; then
        break
      fi
      sleep 0.2
    done
    if is_pid_running "$pid"; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  fi
  rm -f "$file"
}

ensure_binary() {
  if [ ! -d "$SERVICE_DIR" ]; then
    echo "❌ Missing service dir: $SERVICE_DIR"
    exit 1
  fi
  if [ ! -f "$RULES_FILE" ]; then
    echo "❌ Missing rules file: $RULES_FILE"
    exit 1
  fi
  echo "Building mangle-server..."
  (cd "$SERVICE_DIR" && go build -o mangle-server ./server/main.go)
  if [ ! -x "$SERVICE_DIR/mangle-server" ]; then
    echo "❌ Build failed: mangle-server not produced"
    exit 1
  fi
}

ensure_proxy_deps() {
  if [ ! -d "$PROXY_DIR/node_modules" ]; then
    echo "Installing logician-proxy dependencies..."
    (cd "$PROXY_DIR" && npm ci)
  fi
}

wait_for_socket() {
  for _ in $(seq 1 40); do
    [ -S "$SOCK_PATH" ] && return 0
    sleep 0.25
  done
  return 1
}

wait_for_proxy() {
  for _ in $(seq 1 40); do
    if curl -fsS --max-time 2 "http://127.0.0.1:${PROXY_PORT}/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done
  return 1
}

start_linux() {
  ensure_binary
  ensure_proxy_deps
  stop_pid_file "$SERVER_PID_FILE"
  stop_pid_file "$PROXY_PID_FILE"
  pkill -f "$SERVICE_DIR/mangle-server" 2>/dev/null || true
  pkill -f "$PROXY_DIR/proxy.js" 2>/dev/null || true
  rm -f "$SOCK_PATH"

  echo "Starting Logician gRPC service..."
  nohup "$SERVICE_DIR/mangle-server" \
    "--source=$RULES_FILE" \
    "--mode=unix" \
    "--sock-addr=$SOCK_PATH" \
    >"$SERVER_LOG" 2>"$SERVER_ERR" &
  echo $! > "$SERVER_PID_FILE"

  if ! wait_for_socket; then
    echo "❌ Socket did not appear: $SOCK_PATH"
    tail -n 60 "$SERVER_ERR" 2>/dev/null || true
    exit 1
  fi

  echo "Starting Logician HTTP proxy..."
  nohup env PORT="$PROXY_PORT" MANGLE_SOCK="$SOCK_PATH" node "$PROXY_DIR/proxy.js" \
    >"$PROXY_LOG" 2>&1 &
  echo $! > "$PROXY_PID_FILE"

  if ! wait_for_proxy; then
    echo "❌ Proxy did not become healthy on 127.0.0.1:${PROXY_PORT}"
    tail -n 60 "$PROXY_LOG" 2>/dev/null || true
    exit 1
  fi

  echo "✅ Logician started"
  echo "   Socket: $SOCK_PATH"
  echo "   Proxy:  http://127.0.0.1:${PROXY_PORT}"
}

status_linux() {
  local server_pid proxy_pid
  server_pid="$(pid_from_file "$SERVER_PID_FILE")"
  proxy_pid="$(pid_from_file "$PROXY_PID_FILE")"

  if [ -n "${server_pid:-}" ] && is_pid_running "$server_pid"; then
    echo "✅ gRPC service running (pid $server_pid)"
  else
    echo "❌ gRPC service not running"
  fi

  if [ -S "$SOCK_PATH" ]; then
    echo "✅ Socket present: $SOCK_PATH"
  else
    echo "❌ Socket missing: $SOCK_PATH"
  fi

  if [ -n "${proxy_pid:-}" ] && is_pid_running "$proxy_pid"; then
    echo "✅ HTTP proxy running (pid $proxy_pid)"
  else
    echo "❌ HTTP proxy not running"
  fi

  if curl -fsS --max-time 2 "http://127.0.0.1:${PROXY_PORT}/health" >/dev/null 2>&1; then
    echo "✅ Proxy health: OK"
  else
    echo "❌ Proxy health: FAIL"
  fi
}

health_linux() {
  echo "Logician Health Check"
  echo "====================="
  status_linux
  echo
  RESULT=$(curl -fsS --max-time 5 -X POST "http://127.0.0.1:${PROXY_PORT}/query" \
    -H 'content-type: application/json' \
    -d '{"query":"agent(/main)"}' 2>/dev/null || true)
  if echo "$RESULT" | grep -q 'agent(/main)'; then
    COUNT=$(echo "$RESULT" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("count", 0))' 2>/dev/null || echo 0)
    echo "✅ Query path working ($COUNT result(s))"
  else
    echo "❌ Query path failing"
    echo "   $RESULT"
    exit 1
  fi
}

query_linux() {
  local query="${1:-agent(X)}"
  curl -fsS --max-time 10 -X POST "http://127.0.0.1:${PROXY_PORT}/query" \
    -H 'content-type: application/json' \
    -d "{\"query\":$(python3 - <<'PY'
import json,sys
print(json.dumps(sys.argv[1]))
PY
"$query")}" | python3 -m json.tool
}

case "${1:-help}" in
  build)
    ensure_binary
    echo "✅ Build complete"
    ;;
  start)
    if [[ "$(uname)" == "Darwin" ]]; then
      echo "⚠️  Darwin launchctl path is not managed by this Linux-safe script."
      echo "Use the previous macOS install flow if needed."
      exit 1
    fi
    start_linux
    ;;
  stop)
    stop_pid_file "$PROXY_PID_FILE"
    stop_pid_file "$SERVER_PID_FILE"
    pkill -f "$SERVICE_DIR/mangle-server" 2>/dev/null || true
    pkill -f "$PROXY_DIR/proxy.js" 2>/dev/null || true
    rm -f "$SOCK_PATH"
    echo "✅ Logician stopped"
    ;;
  restart)
    "$0" stop
    sleep 1
    "$0" start
    ;;
  status)
    status_linux
    ;;
  health)
    health_linux
    ;;
  query)
    shift || true
    query_linux "${1:-agent(X)}"
    ;;
  logs)
    tail -f "$SERVER_LOG" "$SERVER_ERR" "$PROXY_LOG"
    ;;
  *)
    echo "Logician Control (Linux-safe)"
    echo "=============================="
    echo "Usage: $0 {build|start|stop|restart|status|health|query|logs}"
    ;;
esac
