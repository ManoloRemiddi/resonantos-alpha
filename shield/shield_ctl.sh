#!/bin/bash
# Shield Daemon Control Script (Linux-safe)
# Usage: ./shield_ctl.sh {start|stop|restart|status|health|logs}

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
STATE_DIR="${SHIELD_STATE_DIR:-$HOME/.openclaw/shield}"
PID_FILE="${SHIELD_PID_FILE:-$STATE_DIR/shield.pid}"
LOG_DIR="${SHIELD_LOG_DIR:-$STATE_DIR/logs}"
LOG_FILE="$LOG_DIR/shield_daemon.log"
DAEMON="$REPO_DIR/shield/daemon.py"
HEALTH_HOST="${SHIELD_HEALTH_HOST:-127.0.0.1}"
HEALTH_PORT="${SHIELD_HEALTH_PORT:-9999}"
HEALTH_URL="http://${HEALTH_HOST}:${HEALTH_PORT}/health"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

mkdir -p "$STATE_DIR" "$LOG_DIR"

print_status() { echo -e "${GREEN}✓${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }
print_warn() { echo -e "${YELLOW}!${NC} $1"; }

is_running() {
    local pid=""
    if [[ -f "$PID_FILE" ]]; then
        pid="$(tr -d '[:space:]' < "$PID_FILE")"
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    pgrep -f "$DAEMON" >/dev/null 2>&1
}

get_pid() {
    if [[ -f "$PID_FILE" ]]; then
        tr -d '[:space:]' < "$PID_FILE"
    else
        pgrep -f "$DAEMON" 2>/dev/null | head -1
    fi
}

wait_for_health() {
    for _ in $(seq 1 30); do
        if curl -fsS --max-time 2 "$HEALTH_URL" >/dev/null 2>&1; then
            return 0
        fi
        sleep 0.5
    done
    return 1
}

stop_pid() {
    local pid="$1"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        for _ in $(seq 1 25); do
            if ! kill -0 "$pid" 2>/dev/null; then
                break
            fi
            sleep 0.2
        done
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null || true
        fi
    fi
}

case "${1:-}" in
    start)
        if is_running; then
            print_warn "Shield daemon is already running"
            exit 0
        fi

        echo "Starting Shield daemon..."
        nohup /usr/bin/python3 -u "$DAEMON" >"$LOG_FILE" 2>&1 &
        echo $! > "$PID_FILE"

        if wait_for_health; then
            PID=$(get_pid)
            print_status "Shield daemon started (PID: ${PID:-unknown})"
            print_status "Health endpoint: $HEALTH_URL"
        else
            print_error "Failed to start Shield daemon"
            echo "Check logs: tail -f $LOG_FILE"
            exit 1
        fi
        ;;

    stop)
        PID="$(get_pid || true)"
        if [[ -z "$PID" ]] && ! pgrep -f "$DAEMON" >/dev/null 2>&1; then
            print_warn "Shield daemon is not running"
            exit 0
        fi

        echo "Stopping Shield daemon..."
        stop_pid "$PID"
        pkill -f "$DAEMON" 2>/dev/null || true
        rm -f "$PID_FILE"
        print_status "Shield daemon stopped"
        ;;

    restart)
        "$0" stop || true
        sleep 1
        "$0" start
        ;;

    status)
        echo "Shield Daemon Status"
        echo "===================="
        if is_running; then
            PID="$(get_pid || true)"
            print_status "Running (PID: ${PID:-unknown})"
            echo
            echo "Health check:"
            if curl -fsS --max-time 2 "$HEALTH_URL" > /tmp/shield-health.json 2>/dev/null; then
                cat /tmp/shield-health.json | python3 -m json.tool 2>/dev/null || cat /tmp/shield-health.json
            else
                print_warn "Health endpoint not responding"
            fi
        else
            print_error "Not running"
            exit 1
        fi
        ;;

    health)
        echo "Checking health endpoint..."
        RESPONSE=$(curl -fsS --max-time 5 "$HEALTH_URL" 2>&1) || {
            print_error "Health endpoint not responding (is the daemon running?)"
            exit 1
        }
        print_status "Health endpoint responding"
        echo
        echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
        ;;

    logs)
        if [[ -f "$LOG_FILE" ]]; then
            echo "Tailing Shield daemon logs (Ctrl+C to exit)..."
            echo "Log file: $LOG_FILE"
            echo
            tail -f "$LOG_FILE"
        else
            print_error "Log file not found: $LOG_FILE"
            exit 1
        fi
        ;;

    *)
        echo "Shield Daemon Control (Linux-safe)"
        echo
        echo "Usage: $0 {start|stop|restart|status|health|logs}"
        echo
        echo "Commands:"
        echo "  start   - Start the daemon"
        echo "  stop    - Stop the daemon"
        echo "  restart - Stop and start the daemon"
        echo "  status  - Check if daemon is running and show info"
        echo "  health  - Query the health endpoint"
        echo "  logs    - Tail the daemon log file"
        exit 1
        ;;
esac

exit 0
