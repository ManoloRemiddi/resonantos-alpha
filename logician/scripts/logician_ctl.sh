#!/bin/bash
# Logician Control Script
# Usage: ./logician_ctl.sh [start|stop|status|health|restart|query|logs]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOGICIAN_DIR="$(dirname "$SCRIPT_DIR")"
SERVICE_DIR="$LOGICIAN_DIR/mangle-service"
SOCK_PATH="/tmp/mangle.sock"
PLIST_NAME="com.resonantos.logician"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
LOG_DIR="$LOGICIAN_DIR/logs"

mkdir -p "$LOG_DIR"

# Try grpcurl from common locations
GRPCURL=""
for candidate in "grpcurl" "$HOME/go/bin/grpcurl" "/usr/local/bin/grpcurl"; do
  if command -v "$candidate" &>/dev/null 2>&1 || [ -x "$candidate" ]; then
    GRPCURL="$candidate"
    break
  fi
done

grpc_query() {
  local query="$1"
  if [ -z "$GRPCURL" ]; then
    echo "grpcurl not found. Install: go install github.com/fullstorydev/grpcurl/cmd/grpcurl@latest"
    return 1
  fi
  "$GRPCURL" -plaintext \
    -import-path "$SERVICE_DIR/proto" \
    -proto mangle.proto \
    -d "{\"query\": \"$query\", \"program\": \"\"}" \
    -unix "$SOCK_PATH" \
    mangle.Mangle.Query 2>&1
}

case "${1:-help}" in
  start)
    echo "Starting Logician..."
    if [[ "$(uname)" == "Darwin" ]]; then
      if [ ! -f "$PLIST_PATH" ]; then
        echo "Not installed. Run: ./scripts/install.sh"
        exit 1
      fi
      launchctl load "$PLIST_PATH" 2>/dev/null
      sleep 2
      if [ -S "$SOCK_PATH" ]; then
        echo "✅ Logician started"
      else
        echo "⚠️  Check logs: tail -f $LOG_DIR/logician_error.log"
      fi
    else
      echo "Linux: systemctl start logician"
    fi
    ;;

  stop)
    echo "Stopping Logician..."
    if [[ "$(uname)" == "Darwin" ]]; then
      launchctl unload "$PLIST_PATH" 2>/dev/null
    fi
    pkill -f "mangle-server" 2>/dev/null || true
    echo "✅ Stopped"
    ;;

  restart)
    $0 stop
    sleep 1
    $0 start
    ;;

  status)
    if pgrep -f "mangle-server" > /dev/null; then
      echo "✅ Logician is running"
      if [ -S "$SOCK_PATH" ]; then
        echo "✅ Socket: $SOCK_PATH"
      else
        echo "⚠️  Socket not found"
      fi
    else
      echo "❌ Logician is not running"
    fi
    ;;

  health)
    echo "Logician Health Check"
    echo "===================="
    if ! pgrep -f "mangle-server" > /dev/null; then
      echo "❌ Not running"
      exit 1
    fi
    echo "✅ Process: running"
    
    RESULT=$(grpc_query "agent(X)" 2>&1)
    COUNT=$(echo "$RESULT" | grep -c "answer" || echo "0")
    if [ "$COUNT" -gt 0 ]; then
      echo "✅ gRPC: responding ($COUNT agents found)"
    else
      echo "❌ gRPC: not responding"
      echo "   $RESULT"
      exit 1
    fi
    ;;

  query)
    shift
    QUERY="${1:-agent(X)}"
    if [ -z "$QUERY" ]; then
      echo "Usage: $0 query 'agent(X)'"
      exit 1
    fi
    grpc_query "$QUERY"
    ;;

  logs)
    tail -f "$LOG_DIR/logician.log" "$LOG_DIR/logician_error.log" 2>/dev/null
    ;;

  *)
    echo "Logician Control (ResonantOS)"
    echo "============================="
    echo "Usage: $0 {start|stop|restart|status|health|query|logs}"
    echo ""
    echo "  start     Start the Logician service"
    echo "  stop      Stop the service"
    echo "  restart   Restart the service"
    echo "  status    Check if running"
    echo "  health    Full health check with query test"
    echo "  query     Run a Mangle query: $0 query 'agent(X)'"
    echo "  logs      Tail service logs"
    ;;
esac
