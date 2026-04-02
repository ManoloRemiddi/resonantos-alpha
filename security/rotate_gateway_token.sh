#!/bin/bash
#
# rotate_gateway_token.sh - Gateway Token Rotation Script
# 
# Generates a new cryptographically secure token, updates clawdbot config,
# and restarts the gateway service. All operations are atomic.
#
# COORDINATION-AWARE: Waits for active sessions to complete before rotating
# to avoid interrupting mid-generation API calls.
#
# Part of ResonantOS Security Layer
# https://github.com/resonantos
#

set -euo pipefail

# === Configuration ===
CONFIG_FILE="${HOME}/.clawdbot/clawdbot.json"
LOG_DIR="${HOME}/Library/Logs/resonantos"
LOG_FILE="${LOG_DIR}/token_rotation.log"
BACKUP_DIR="${HOME}/.clawdbot/backups"
TOKEN_LENGTH=24  # 24 bytes = 48 hex chars (192 bits entropy)

# === Coordination Settings ===
ACTIVE_THRESHOLD_MS=60000   # Consider session "active" if activity within 60 seconds
WAIT_INTERVAL_SEC=30        # Wait 30 seconds between busy checks
MAX_WAIT_RETRIES=10         # Max 10 retries = 5 minutes total wait
FORCE_AFTER_WAIT=true       # Force rotation after max wait (safety override)

# === Colors (disabled in non-interactive) ===
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    NC=''
fi

# === Logging ===
log() {
    local level="$1"
    shift
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local message="$*"
    
    # Ensure log directory exists
    mkdir -p "$LOG_DIR"
    
    # Log to file
    echo "${timestamp} | ${level} | ${message}" >> "$LOG_FILE"
    
    # Also output to stderr if interactive or error
    if [[ -t 1 ]] || [[ "$level" == "ERROR" ]]; then
        case "$level" in
            ERROR)   echo -e "${RED}[ERROR]${NC} ${message}" >&2 ;;
            SUCCESS) echo -e "${GREEN}[OK]${NC} ${message}" ;;
            WARN)    echo -e "${YELLOW}[WARN]${NC} ${message}" ;;
            *)       echo "[${level}] ${message}" ;;
        esac
    fi
}

die() {
    log "ERROR" "$*"
    exit 1
}

# === Coordination Functions ===

# Get active session count from gateway API
# Returns: count of sessions with activity within ACTIVE_THRESHOLD_MS
get_active_sessions() {
    local status_json active_count
    
    # Query gateway status via clawdbot CLI
    status_json=$(clawdbot gateway call status --json 2>/dev/null) || {
        log "WARN" "Could not query gateway status (gateway may be down)"
        echo "0"  # Assume idle if can't check
        return
    }
    
    # Extract sessions with age < threshold
    # age is in milliseconds since last activity
    active_count=$(echo "$status_json" | jq -r --argjson threshold "$ACTIVE_THRESHOLD_MS" '
        [.sessions.recent[]? | select(.age < $threshold)] | length
    ' 2>/dev/null) || {
        log "WARN" "Failed to parse gateway session data"
        echo "0"
        return
    }
    
    echo "${active_count:-0}"
}

# Get details of active sessions for logging
get_active_session_details() {
    local status_json
    
    status_json=$(clawdbot gateway call status --json 2>/dev/null) || {
        echo "unknown"
        return
    }
    
    # Return list of active agent IDs
    echo "$status_json" | jq -r --argjson threshold "$ACTIVE_THRESHOLD_MS" '
        [.sessions.recent[]? | select(.age < $threshold) | .agentId] | unique | join(", ")
    ' 2>/dev/null || echo "unknown"
}

# Wait for active sessions to complete before rotation
# Returns: 0 if clear to rotate, 1 if forced after timeout
wait_for_idle() {
    local retry_count=0
    local active_count
    local active_agents
    
    log "INFO" "Checking for active sessions before rotation..."
    
    while [[ $retry_count -lt $MAX_WAIT_RETRIES ]]; do
        active_count=$(get_active_sessions)
        
        if [[ "$active_count" -eq 0 ]]; then
            if [[ $retry_count -eq 0 ]]; then
                log "SUCCESS" "All agents idle — rotating immediately"
            else
                log "SUCCESS" "All agents now idle after ${retry_count} checks — proceeding with rotation"
            fi
            return 0
        fi
        
        # Get which agents are active for better logging
        active_agents=$(get_active_session_details)
        
        retry_count=$((retry_count + 1))
        local remaining=$((MAX_WAIT_RETRIES - retry_count))
        local wait_remaining=$((remaining * WAIT_INTERVAL_SEC))
        
        log "WARN" "Waiting for active sessions to complete..."
        log "INFO" "  Active agents: ${active_agents} | Sessions: ${active_count}"
        log "INFO" "  Retry ${retry_count}/${MAX_WAIT_RETRIES} | Will force rotate in ${wait_remaining}s"
        
        sleep "$WAIT_INTERVAL_SEC"
    done
    
    # Max retries exceeded
    if [[ "$FORCE_AFTER_WAIT" == "true" ]]; then
        active_agents=$(get_active_session_details)
        log "WARN" "⚠️  FORCING ROTATION after 5min wait — active agents may be interrupted"
        log "WARN" "  Still active: ${active_agents}"
        return 1  # Indicate forced rotation
    else
        log "ERROR" "Max wait time exceeded and FORCE_AFTER_WAIT=false — aborting rotation"
        exit 1
    fi
}

# === Token Utilities ===
generate_token() {
    openssl rand -hex "$TOKEN_LENGTH"
}

hash_token() {
    local token="$1"
    echo -n "$token" | shasum -a 256 | cut -d' ' -f1 | head -c 16
}

# === Pre-flight Checks ===
preflight_checks() {
    log "INFO" "Running preflight checks..."
    
    # Check config file exists
    [[ -f "$CONFIG_FILE" ]] || die "Config file not found: $CONFIG_FILE"
    
    # Check config file is readable
    [[ -r "$CONFIG_FILE" ]] || die "Config file not readable: $CONFIG_FILE"
    
    # Check config file is writable
    [[ -w "$CONFIG_FILE" ]] || die "Config file not writable: $CONFIG_FILE"
    
    # Check jq is available
    command -v jq >/dev/null 2>&1 || die "jq is required but not installed"
    
    # Check openssl is available
    command -v openssl >/dev/null 2>&1 || die "openssl is required but not installed"
    
    # Check clawdbot is available
    command -v clawdbot >/dev/null 2>&1 || die "clawdbot is required but not installed"
    
    # Validate JSON structure
    jq -e '.gateway.auth.token' "$CONFIG_FILE" >/dev/null 2>&1 || \
        die "Config file missing .gateway.auth.token field"
    
    log "INFO" "Preflight checks passed"
}

# === Backup ===
create_backup() {
    mkdir -p "$BACKUP_DIR"
    local backup_name="clawdbot.json.$(date '+%Y%m%d_%H%M%S').bak"
    cp "$CONFIG_FILE" "${BACKUP_DIR}/${backup_name}"
    log "INFO" "Backup created: ${backup_name}"
    
    # Keep only last 30 backups
    find "$BACKUP_DIR" -name "clawdbot.json.*.bak" -type f | \
        sort -r | tail -n +31 | xargs -r rm -f
}

# === Rotation ===
rotate_token() {
    log "INFO" "Starting token rotation..."
    
    # Get current token for audit log
    local old_token=$(jq -r '.gateway.auth.token' "$CONFIG_FILE")
    local old_token_hash=$(hash_token "$old_token")
    
    # Generate new token
    local new_token=$(generate_token)
    local new_token_hash=$(hash_token "$new_token")
    
    log "INFO" "Generated new token (hash: ${new_token_hash}...)"
    
    # Create backup before modification
    create_backup
    
    # Atomic update: write to temp file, then move
    local temp_file=$(mktemp)
    if ! jq --arg token "$new_token" '.gateway.auth.token = $token' "$CONFIG_FILE" > "$temp_file"; then
        rm -f "$temp_file"
        die "Failed to update config with jq"
    fi
    
    # Validate the new config is valid JSON
    if ! jq -e '.' "$temp_file" >/dev/null 2>&1; then
        rm -f "$temp_file"
        die "Generated invalid JSON, aborting"
    fi
    
    # Atomic move
    mv "$temp_file" "$CONFIG_FILE"
    
    log "SUCCESS" "Config updated atomically"
    log "INFO" "Rotated token | Old: ${old_token_hash}... | New: ${new_token_hash}..."
    
    # Restart gateway
    restart_gateway
    
    log "SUCCESS" "Token rotation complete"
}

# === Gateway Restart ===
restart_gateway() {
    log "INFO" "Restarting gateway..."
    
    local start_time=$(date +%s)
    
    # Use clawdbot gateway restart
    if clawdbot gateway restart >/dev/null 2>&1; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        log "SUCCESS" "Gateway restarted in ${duration}s"
    else
        # Fallback: try stop then start
        log "WARN" "Restart failed, trying stop+start..."
        clawdbot gateway stop >/dev/null 2>&1 || true
        sleep 1
        if clawdbot gateway start >/dev/null 2>&1; then
            log "SUCCESS" "Gateway started after stop"
        else
            die "Failed to restart gateway"
        fi
    fi
    
    # Brief wait for gateway to be ready
    sleep 1
    
    # Verify gateway is running
    if clawdbot gateway status >/dev/null 2>&1; then
        log "SUCCESS" "Gateway verified running"
    else
        log "WARN" "Could not verify gateway status (may still be starting)"
    fi
}

# === Main ===
main() {
    local force_flag=""
    local skip_coordination=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --force|-f)
                skip_coordination=true
                shift
                ;;
            --no-wait)
                skip_coordination=true
                shift
                ;;
            *)
                shift
                ;;
        esac
    done
    
    log "INFO" "=== Token Rotation Started ==="
    
    preflight_checks
    
    # Coordination: wait for active sessions unless --force
    if [[ "$skip_coordination" == "true" ]]; then
        log "INFO" "Skipping coordination check (--force flag)"
    else
        if wait_for_idle; then
            force_flag=""
        else
            force_flag=" (forced after wait)"
        fi
    fi
    
    rotate_token
    
    log "INFO" "=== Token Rotation Finished${force_flag} ==="
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
