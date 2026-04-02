#!/bin/bash
#
# Shield Daemon Control Script
# Usage: ./shield_ctl.sh {start|stop|restart|status|health|logs}
#

PLIST_NAME="com.resonantos.shield"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
PID_FILE="$HOME/clawd/security/shield/shield.pid"
LOG_FILE="$HOME/clawd/security/logs/shield_daemon.log"
HEALTH_URL="http://127.0.0.1:9999/health"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}!${NC} $1"
}

check_plist() {
    if [[ ! -f "$PLIST_PATH" ]]; then
        print_error "Plist not found at $PLIST_PATH"
        exit 1
    fi
}

is_running() {
    launchctl list 2>/dev/null | grep -q "$PLIST_NAME"
    return $?
}

get_pid() {
    if [[ -f "$PID_FILE" ]]; then
        cat "$PID_FILE"
    else
        # Try to find via pgrep
        pgrep -f "shield/daemon.py" 2>/dev/null | head -1
    fi
}

case "$1" in
    start)
        check_plist
        if is_running; then
            print_warn "Shield daemon is already running"
            exit 0
        fi
        
        echo "Starting Shield daemon..."
        launchctl load "$PLIST_PATH"
        
        # Wait a moment for startup
        sleep 2
        
        if is_running; then
            PID=$(get_pid)
            print_status "Shield daemon started (PID: ${PID:-unknown})"
        else
            print_error "Failed to start Shield daemon"
            echo "Check logs: tail -f $LOG_FILE"
            exit 1
        fi
        ;;
        
    stop)
        if ! is_running; then
            print_warn "Shield daemon is not running"
            exit 0
        fi
        
        echo "Stopping Shield daemon..."
        launchctl unload "$PLIST_PATH" 2>/dev/null
        
        # Give it a moment
        sleep 1
        
        # Force kill if still running
        PID=$(get_pid)
        if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
            print_warn "Daemon still running, sending SIGTERM..."
            kill "$PID" 2>/dev/null
            sleep 1
        fi
        
        if is_running; then
            print_error "Failed to stop Shield daemon"
            exit 1
        else
            print_status "Shield daemon stopped"
        fi
        ;;
        
    restart)
        $0 stop
        sleep 1
        $0 start
        ;;
        
    status)
        echo "Shield Daemon Status"
        echo "===================="
        
        if is_running; then
            PID=$(get_pid)
            print_status "Running (PID: ${PID:-unknown})"
            
            # Show launchctl info
            echo ""
            echo "Launchctl status:"
            launchctl list 2>/dev/null | grep "$PLIST_NAME" || echo "  (no details)"
            
            # Try health check
            echo ""
            echo "Health check:"
            if curl -s --max-time 2 "$HEALTH_URL" > /dev/null 2>&1; then
                curl -s "$HEALTH_URL" | python3 -m json.tool 2>/dev/null || curl -s "$HEALTH_URL"
            else
                print_warn "Health endpoint not responding"
            fi
        else
            print_error "Not running"
        fi
        ;;
        
    health)
        echo "Checking health endpoint..."
        RESPONSE=$(curl -s --max-time 5 "$HEALTH_URL" 2>&1)
        CURL_EXIT=$?
        
        if [[ $CURL_EXIT -eq 0 ]]; then
            print_status "Health endpoint responding"
            echo ""
            echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
        else
            print_error "Health endpoint not responding (is the daemon running?)"
            exit 1
        fi
        ;;
        
    logs)
        if [[ -f "$LOG_FILE" ]]; then
            echo "Tailing Shield daemon logs (Ctrl+C to exit)..."
            echo "Log file: $LOG_FILE"
            echo ""
            tail -f "$LOG_FILE"
        else
            print_error "Log file not found: $LOG_FILE"
            exit 1
        fi
        ;;
        
    *)
        echo "Shield Daemon Control"
        echo ""
        echo "Usage: $0 {start|stop|restart|status|health|logs}"
        echo ""
        echo "Commands:"
        echo "  start   - Load and start the daemon via launchd"
        echo "  stop    - Unload and stop the daemon"
        echo "  restart - Stop and start the daemon"
        echo "  status  - Check if daemon is running and show info"
        echo "  health  - Query the health endpoint"
        echo "  logs    - Tail the daemon log file"
        exit 1
        ;;
esac

exit 0
