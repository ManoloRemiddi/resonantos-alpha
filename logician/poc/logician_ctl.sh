#!/bin/bash
# Logician Daemon Control Script
# Usage: ./logician_ctl.sh [start|stop|status|health|restart|install|uninstall|logs]

PLIST_NAME="com.resonantos.logician"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
LOGICIAN_DIR="$HOME/clawd/projects/logician/poc"
MANGLE_SERVICE="$LOGICIAN_DIR/mangle-service"
RULES_FILE="$LOGICIAN_DIR/demo_rules.mg"
LOG_DIR="$HOME/clawd/projects/logician/logs"
HEALTH_URL="http://127.0.0.1:8080"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

case "$1" in
    start)
        echo "Starting Logician daemon..."
        if [ ! -f "$PLIST_PATH" ]; then
            echo "Error: LaunchAgent plist not found at $PLIST_PATH"
            echo "Run: ./logician_ctl.sh install"
            exit 1
        fi
        launchctl load "$PLIST_PATH" 2>/dev/null
        sleep 2
        if pgrep -f "mangle-server" > /dev/null; then
            echo "✅ Logician daemon started successfully"
            echo "   Mangle gRPC server running on port 8080"
        else
            echo "⚠️  Daemon loaded but process not found"
            echo "Check logs: tail -f $LOG_DIR/logician_error.log"
        fi
        ;;
        
    stop)
        echo "Stopping Logician daemon..."
        launchctl unload "$PLIST_PATH" 2>/dev/null
        # Also kill any lingering process
        pkill -f "mangle-server" 2>/dev/null
        echo "✅ Logician daemon stopped"
        ;;
        
    restart)
        $0 stop
        sleep 1
        $0 start
        ;;
        
    status)
        if launchctl list | grep -q "$PLIST_NAME"; then
            echo "✅ Logician daemon is loaded"
        else
            echo "❌ Logician daemon is not loaded"
        fi
        # Check if process is running
        if pgrep -f "mangle-server" > /dev/null; then
            echo "✅ mangle-server process is running"
            # Test gRPC query
            RESULT=$("$HOME/go/bin/grpcurl" -plaintext \
                -import-path "$MANGLE_SERVICE/proto" \
                -proto mangle.proto \
                -d '{"query": "agent(X)", "program": ""}' \
                localhost:8080 mangle.Mangle.Query 2>&1 | grep -c "answer" || echo "0")
            if [ "$RESULT" -gt 0 ]; then
                echo "✅ Mangle gRPC server responding ($RESULT agents found)"
            else
                echo "⚠️  Mangle server not responding to queries"
            fi
        else
            echo "❌ mangle-server process is not running"
        fi
        ;;
        
    health)
        echo "Logician Health Check"
        echo "===================="
        if pgrep -f "mangle-server" > /dev/null; then
            echo "✅ mangle-server process: RUNNING"
            # Test a gRPC query
            RESULT=$("$HOME/go/bin/grpcurl" -plaintext \
                -import-path "$MANGLE_SERVICE/proto" \
                -proto mangle.proto \
                -d '{"query": "agent(X)", "program": ""}' \
                localhost:8080 mangle.Mangle.Query 2>&1 | grep -c "answer" || echo "0")
            if [ "$RESULT" -gt 0 ]; then
                echo "✅ gRPC queries: WORKING ($RESULT agents found)"
            else
                echo "❌ gRPC queries: FAILING"
                exit 1
            fi
        else
            echo "❌ mangle-server process: NOT RUNNING"
            exit 1
        fi
        ;;
        
    query)
        # Quick query helper
        shift
        QUERY="$1"
        if [ -z "$QUERY" ]; then
            echo "Usage: ./logician_ctl.sh query 'agent(X)'"
            exit 1
        fi
        "$HOME/go/bin/grpcurl" -plaintext \
            -import-path "$MANGLE_SERVICE/proto" \
            -proto mangle.proto \
            -d "{\"query\": \"$QUERY\", \"program\": \"\"}" \
            localhost:8080 mangle.Mangle.Query
        ;;
        
    install)
        echo "Installing Logician LaunchAgent..."
        
        # Build mangle-server if not exists
        if [ ! -f "$MANGLE_SERVICE/mangle-server" ]; then
            echo "Building mangle-server..."
            cd "$MANGLE_SERVICE" && go build -o mangle-server ./server/main.go
        fi
        
        mkdir -p "$HOME/Library/LaunchAgents"
        mkdir -p "$LOG_DIR"
        
        cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>$MANGLE_SERVICE/mangle-server</string>
        <string>--source=$RULES_FILE</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$MANGLE_SERVICE</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/logician.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/logician_error.log</string>
</dict>
</plist>
EOF
        echo "✅ LaunchAgent installed at $PLIST_PATH"
        echo "Run './logician_ctl.sh start' to start the daemon"
        ;;
        
    uninstall)
        echo "Uninstalling Logician LaunchAgent..."
        $0 stop 2>/dev/null
        rm -f "$PLIST_PATH"
        echo "✅ LaunchAgent removed"
        ;;
        
    logs)
        tail -f "$LOG_DIR/logician.log"
        ;;
        
    test)
        echo "Running Logician Demo..."
        python3 "$LOGICIAN_DIR/logician_client.py"
        ;;
        
    *)
        echo "Logician Daemon Control (ResonantOS)"
        echo "===================================="
        echo "Usage: $0 {start|stop|restart|status|health|query|install|uninstall|logs|test}"
        echo ""
        echo "Commands:"
        echo "  install   - Create LaunchAgent plist and build server"
        echo "  start     - Start the daemon"
        echo "  stop      - Stop the daemon"
        echo "  restart   - Restart the daemon"
        echo "  status    - Check if daemon is running"
        echo "  health    - Full health check with query test"
        echo "  query     - Run a Mangle query (e.g., ./logician_ctl.sh query 'agent(X)')"
        echo "  logs      - Tail the daemon logs"
        echo "  test      - Run the Python demo"
        echo "  uninstall - Remove LaunchAgent"
        exit 1
        ;;
esac
