#!/bin/bash
# Logician Installation Script
# Builds the Mangle gRPC server and sets up the service.
#
# Usage: ./install.sh [--rules path/to/rules.mg]
#
# Prerequisites: Go 1.22+

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOGICIAN_DIR="$(dirname "$SCRIPT_DIR")"
SERVICE_DIR="$LOGICIAN_DIR/mangle-service"
RULES_FILE="${1:-$LOGICIAN_DIR/rules/example-rules.mg}"
SOCK_PATH="/tmp/mangle.sock"

echo "========================================"
echo "  Logician — Deterministic Policy Engine"
echo "========================================"
echo ""

# Check Go
if ! command -v go &>/dev/null; then
  echo "❌ Go is not installed."
  echo "   Install: brew install go (macOS) or see https://golang.org/dl/"
  exit 1
fi

GO_VERSION=$(go version | grep -oP '1\.\d+' | head -1)
echo "✅ Go installed ($(go version))"

# Build the server
echo ""
echo "Building Mangle gRPC server..."
cd "$SERVICE_DIR"
go get ./...
go build -o mangle-server ./server/main.go

if [ ! -f "$SERVICE_DIR/mangle-server" ]; then
  echo "❌ Build failed"
  exit 1
fi

echo "✅ Server built: $SERVICE_DIR/mangle-server"

# Verify rules file
if [ ! -f "$RULES_FILE" ]; then
  echo "⚠️  Rules file not found: $RULES_FILE"
  echo "   Using default example rules"
  RULES_FILE="$LOGICIAN_DIR/rules/example-rules.mg"
fi
echo "✅ Rules: $RULES_FILE"

# Install LaunchAgent (macOS) or show systemd instructions (Linux)
if [[ "$(uname)" == "Darwin" ]]; then
  PLIST_NAME="com.resonantos.logician"
  PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
  LOG_DIR="$LOGICIAN_DIR/logs"
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
        <string>$SERVICE_DIR/mangle-server</string>
        <string>--source=$RULES_FILE</string>
        <string>--mode=unix</string>
        <string>--sock-addr=$SOCK_PATH</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$SERVICE_DIR</string>
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

  echo "✅ LaunchAgent installed: $PLIST_PATH"

  # Start the service
  launchctl unload "$PLIST_PATH" 2>/dev/null || true
  launchctl load "$PLIST_PATH"
  sleep 2

  if [ -S "$SOCK_PATH" ]; then
    echo "✅ Logician is running (socket: $SOCK_PATH)"
  else
    echo "⚠️  Socket not found. Check logs: tail -f $LOG_DIR/logician_error.log"
  fi

else
  echo ""
  echo "📝 For Linux, create a systemd service:"
  echo ""
  echo "   [Unit]"
  echo "   Description=Logician Mangle Service"
  echo "   After=network.target"
  echo ""
  echo "   [Service]"
  echo "   ExecStart=$SERVICE_DIR/mangle-server --source=$RULES_FILE --mode=unix --sock-addr=$SOCK_PATH"
  echo "   Restart=always"
  echo ""
  echo "   [Install]"
  echo "   WantedBy=multi-user.target"
  echo ""
  echo "   Save to: /etc/systemd/system/logician.service"
  echo "   Then: systemctl enable --now logician"
fi

echo ""
echo "========================================"
echo "  Installation Complete"
echo "========================================"
echo ""
echo "Test it:"
echo "  ./scripts/logician_ctl.sh query 'agent(X)'"
echo "  python3 client/logician_client.py"
echo ""
echo "Manage:"
echo "  ./scripts/logician_ctl.sh status"
echo "  ./scripts/logician_ctl.sh restart"
echo ""
