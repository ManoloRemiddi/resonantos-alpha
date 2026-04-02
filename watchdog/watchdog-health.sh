#!/bin/bash
# Watchdog Health Monitor
# Restarts watchdog if no log entries for 5 minutes
# Run as a separate process from watchdog

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/watchdog.log"
WATCHDOG_SCRIPT="$SCRIPT_DIR/watchdog.py"
HEALTH_THRESHOLD=300  # 5 minutes in seconds

log_msg() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] HEALTH: $1"
}

while true; do
    if [ -f "$LOG_FILE" ]; then
        # Get time since last log entry
        LAST_MOD=$(stat -f %m "$LOG_FILE" 2>/dev/null || stat -c %Y "$LOG_FILE" 2>/dev/null)
        CURRENT_TIME=$(date +%s)
        AGE=$((CURRENT_TIME - LAST_MOD))
        
        if [ $AGE -gt $HEALTH_THRESHOLD ]; then
            log_msg "Watchdog log stale ($AGE seconds old), restarting watchdog..."
            
            # Kill existing watchdog
            pkill -f "watchdog.py" 2>/dev/null
            sleep 2
            
            # Restart watchdog
            nohup /opt/homebrew/bin/python3 "$WATCHDOG_SCRIPT" >> "$LOG_FILE" 2>&1 &
            log_msg "Watchdog restarted"
        else
            log_msg "Watchdog healthy (last log $AGE seconds ago)"
        fi
    else
        log_msg "Watchdog log file missing, starting watchdog..."
        nohup /opt/homebrew/bin/python3 "$WATCHDOG_SCRIPT" >> "$LOG_FILE" 2>&1 &
    fi
    
    sleep 60  # Check every minute
done
